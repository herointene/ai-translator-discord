"""
Discord AI Translator - Database Module

Handles SQLite persistence for messages with support for:
- Saving messages with thread/channel context
- Retrieving recent context for translation requests
- Topic filtering support (raw context retrieval for AI filtering)
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading


class MessageDatabase:
    """
    SQLite database handler for Discord messages.
    
    Supports the Topic Filtering design by providing raw recent context
    that can be filtered by AI in Task 3.
    """
    
    def __init__(self, db_path: str = "messages.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_database()
    
    @property
    def _connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_database(self) -> None:
        """Initialize database schema."""
        with self._connection:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    msg_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    thread_id TEXT,
                    guild_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index for efficient context queries
            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_channel_time 
                ON messages(channel_id, timestamp DESC)
            """)
            
            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_thread_time 
                ON messages(thread_id, timestamp DESC)
            """)
    
    def save_message(
        self,
        msg_id: str,
        user_id: str,
        user_name: str,
        content: str,
        timestamp: str,
        channel_id: str,
        thread_id: Optional[str] = None,
        guild_id: Optional[str] = None
    ) -> bool:
        """
        Save a message to the database.
        
        Args:
            msg_id: Discord message ID
            user_id: Discord user ID
            user_name: Discord username
            content: Message content
            timestamp: ISO format timestamp
            channel_id: Discord channel ID
            thread_id: Discord thread ID (if in a thread)
            guild_id: Discord guild/server ID
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT OR REPLACE INTO messages 
                    (msg_id, user_id, user_name, content, timestamp, channel_id, thread_id, guild_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (msg_id, user_id, user_name, content, timestamp, channel_id, thread_id, guild_id)
                )
            return True
        except sqlite3.Error as e:
            print(f"[Database] Error saving message {msg_id}: {e}")
            return False
    
    def get_message(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific message by ID.
        
        Args:
            msg_id: Discord message ID
            
        Returns:
            Message dict or None if not found
        """
        try:
            cursor = self._connection.execute(
                "SELECT * FROM messages WHERE msg_id = ?",
                (msg_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"[Database] Error retrieving message {msg_id}: {e}")
            return None
    
    def get_relevant_context(
        self,
        msg_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages in the same channel/thread for context.
        
        This provides raw context that will be filtered by AI in Task 3
        to identify semantically related messages (topic filtering).
        
        Args:
            msg_id: The target message ID to get context for
            limit: Maximum number of context messages to retrieve
            
        Returns:
            List of message dicts, ordered by timestamp (oldest first)
        """
        try:
            # First, get the target message to determine channel/thread
            target = self.get_message(msg_id)
            if not target:
                print(f"[Database] Target message {msg_id} not found")
                return []
            
            channel_id = target['channel_id']
            thread_id = target['thread_id']
            target_time = target['timestamp']
            
            # Query for recent messages in the same context
            # Prioritize thread context if available, otherwise channel
            if thread_id:
                # In a thread - get messages from the same thread
                cursor = self._connection.execute(
                    """
                    SELECT * FROM messages 
                    WHERE thread_id = ? 
                    AND timestamp <= ?
                    AND msg_id != ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (thread_id, target_time, msg_id, limit)
                )
            else:
                # Not in a thread - get messages from the same channel
                # Exclude messages that are in threads (they have separate context)
                cursor = self._connection.execute(
                    """
                    SELECT * FROM messages 
                    WHERE channel_id = ? 
                    AND thread_id IS NULL
                    AND timestamp <= ?
                    AND msg_id != ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (channel_id, target_time, msg_id, limit)
                )
            
            rows = cursor.fetchall()
            
            # Convert to dicts and reverse to get chronological order (oldest first)
            messages = [dict(row) for row in reversed(rows)]
            
            print(f"[Database] Retrieved {len(messages)} context messages for {msg_id}")
            return messages
            
        except sqlite3.Error as e:
            print(f"[Database] Error getting context for {msg_id}: {e}")
            return []
    
    def get_recent_messages(
        self,
        channel_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages from a channel or thread.
        
        Args:
            channel_id: Discord channel ID
            thread_id: Discord thread ID (takes precedence over channel_id)
            limit: Maximum number of messages
            
        Returns:
            List of message dicts, ordered by timestamp (newest first)
        """
        try:
            if thread_id:
                cursor = self._connection.execute(
                    """
                    SELECT * FROM messages 
                    WHERE thread_id = ? 
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (thread_id, limit)
                )
            elif channel_id:
                cursor = self._connection.execute(
                    """
                    SELECT * FROM messages 
                    WHERE channel_id = ? AND thread_id IS NULL
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (channel_id, limit)
                )
            else:
                return []
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            print(f"[Database] Error retrieving recent messages: {e}")
            return []
    
    def delete_old_messages(self, days: int = 30) -> int:
        """
        Delete messages older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of deleted messages
        """
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    DELETE FROM messages 
                    WHERE timestamp < datetime('now', '-{} days')
                    """.format(days)
                )
                deleted = cursor.rowcount
                print(f"[Database] Deleted {deleted} old messages")
                return deleted
        except sqlite3.Error as e:
            print(f"[Database] Error deleting old messages: {e}")
            return 0
    
    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton instance for easy import
db = MessageDatabase()


# Convenience functions for direct use
def save_message(
    msg_id: str,
    user_id: str,
    user_name: str,
    content: str,
    timestamp: str,
    channel_id: str,
    thread_id: Optional[str] = None,
    guild_id: Optional[str] = None
) -> bool:
    """Save a message using the default database instance."""
    return db.save_message(msg_id, user_id, user_name, content, timestamp, channel_id, thread_id, guild_id)


def get_relevant_context(msg_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get relevant context using the default database instance."""
    return db.get_relevant_context(msg_id, limit)


def get_message(msg_id: str) -> Optional[Dict[str, Any]]:
    """Get a message by ID using the default database instance."""
    return db.get_message(msg_id)
