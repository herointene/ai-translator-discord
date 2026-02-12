"""
Discord AI Translator - Bot Module

Core Discord bot implementation using discord.py.

Features:
- Saves all messages to SQLite database for context
- Listens for 🌐 reaction to trigger translation
- Retrieves relevant context from database
- Placeholder for Topic Filtering (to be refined in Task 4)
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands

from database import db, save_message, get_relevant_context, get_message


# Configuration from environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TRANSLATION_EMOJI = "🌐"

# Intents configuration
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True


class AITranslatorBot(commands.Bot):
    """
    Discord AI Translator Bot.
    
    Automatically saves messages to database and responds to 🌐 reactions
    for translation requests with intelligent context filtering.
    """
    
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.db = db
    
    async def setup_hook(self):
        """Called when the bot is starting up."""
        print(f"[Bot] Logged in as {self.user} (ID: {self.user.id})")
        print("[Bot] AI Translator Bot is ready!")
    
    async def on_ready(self):
        """Called when the bot has connected to Discord."""
        print(f"[Bot] Connected to {len(self.guilds)} guilds")
        for guild in self.guilds:
            print(f"  - {guild.name} (ID: {guild.id})")
    
    async def on_message(self, message: discord.Message):
        """
        Handle incoming messages - save to database for context.
        
        This is the core message persistence logic that enables
        intelligent context retrieval for translation requests.
        """
        # Ignore bot messages to avoid loops
        if message.author.bot:
            return
        
        # Save message to database
        await self._save_message_to_db(message)
        
        # Process commands (if any)
        await self.process_commands(message)
    
    async def _save_message_to_db(self, message: discord.Message):
        """Save a Discord message to the SQLite database."""
        try:
            # Extract thread ID if message is in a thread
            thread_id = None
            if isinstance(message.channel, discord.Thread):
                thread_id = str(message.channel.id)
            
            # Format timestamp as ISO string
            timestamp = message.created_at.isoformat()
            
            # Save to database
            success = save_message(
                msg_id=str(message.id),
                user_id=str(message.author.id),
                user_name=message.author.display_name,
                content=message.content,
                timestamp=timestamp,
                channel_id=str(message.channel.id),
                thread_id=thread_id,
                guild_id=str(message.guild.id) if message.guild else None
            )
            
            if success:
                print(f"[Bot] Saved message {message.id} from {message.author.display_name}")
            else:
                print(f"[Bot] Failed to save message {message.id}")
                
        except Exception as e:
            print(f"[Bot] Error saving message {message.id}: {e}")
    
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        Handle reaction add events - trigger translation on 🌐 emoji.
        
        Uses raw reaction event to catch reactions on messages not in cache.
        """
        # Check if it's the translation emoji
        if str(payload.emoji) != TRANSLATION_EMOJI:
            return
        
        # Ignore bot's own reactions
        if payload.user_id == self.user.id:
            return
        
        print(f"[Bot] Translation triggered for message {payload.message_id} by user {payload.user_id}")
        
        # Process translation request
        await self._handle_translation_request(payload)
    
    async def _handle_translation_request(self, payload: discord.RawReactionActionEvent):
        """
        Handle a translation request triggered by 🌐 reaction.
        
        Steps:
        1. Fetch the message to be translated
        2. Retrieve recent context from database
        3. Apply topic filtering (placeholder for Task 4)
        4. Send translation result
        """
        try:
            # Get the channel
            channel = self.get_channel(payload.channel_id)
            if not channel:
                print(f"[Bot] Channel {payload.channel_id} not found")
                return
            
            # Fetch the message to translate
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                print(f"[Bot] Message {payload.message_id} not found")
                return
            except discord.Forbidden:
                print(f"[Bot] No permission to fetch message {payload.message_id}")
                return
            
            # Get user who triggered the translation
            user = self.get_user(payload.user_id)
            user_name = user.display_name if user else f"User {payload.user_id}"
            
            print(f"[Bot] Translating message from {message.author.display_name} for {user_name}")
            
            # Step 1: Retrieve raw context from database
            raw_context = get_relevant_context(str(message.id), limit=10)
            print(f"[Bot] Retrieved {len(raw_context)} raw context messages")
            
            # Step 2: Apply topic filtering (placeholder for Task 4)
            # This will be refined in Task 4 with actual AI-based filtering
            filtered_context = await self._filter_context_by_topic(message.content, raw_context)
            
            # Step 3: Send acknowledgment (placeholder translation)
            # Full translation logic will be implemented in Task 4
            await self._send_translation_response(channel, message, filtered_context, user)
            
        except Exception as e:
            print(f"[Bot] Error handling translation request: {e}")
            import traceback
            traceback.print_exc()
    
    async def _filter_context_by_topic(
        self, 
        target_content: str, 
        raw_context: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter context messages to keep only topic-relevant ones.
        
        This is a placeholder implementation for Task 3.
        In Task 4, this will be enhanced with AI-based semantic filtering
        using MiMo-V2 or Kimi API.
        
        Current simple logic:
        - Returns all context (no filtering yet)
        - Logs the filtering attempt for debugging
        
        Args:
            target_content: The message content to translate
            raw_context: List of raw context messages from database
            
        Returns:
            Filtered list of relevant context messages
        """
        print(f"[TopicFilter] Target message: {target_content[:100]}...")
        print(f"[TopicFilter] Raw context count: {len(raw_context)}")
        
        # Placeholder: Return all context for now
        # TODO: Implement AI-based topic filtering in Task 4
        # The AI will analyze the target message and context to:
        # 1. Identify the main topic of the target message
        # 2. Score each context message for relevance
        # 3. Return only messages above a relevance threshold
        
        if raw_context:
            print(f"[TopicFilter] Context preview (last 3):")
            for ctx in raw_context[-3:]:
                print(f"  - {ctx['user_name']}: {ctx['content'][:50]}...")
        
        # For now, return all context messages
        # This maintains conversation flow while we develop the AI filter
        return raw_context
    
    async def _send_translation_response(
        self,
        channel: discord.TextChannel,
        message: discord.Message,
        context: List[Dict[str, Any]],
        requesting_user: Optional[discord.User]
    ):
        """
        Send translation response to the channel.
        
        This is a placeholder implementation. In Task 4, this will:
        1. Call the translation API with context
        2. Format the response with translation + explanation
        3. Handle language detection and instruction parsing
        """
        # Create a simple acknowledgment embed
        embed = discord.Embed(
            title="🌐 Translation Request Received",
            description=f"Translation for message from {message.author.display_name}",
            color=0x3498db,
            timestamp=datetime.now()
        )
        
        # Add the original message content
        embed.add_field(
            name="Original Message",
            value=message.content[:1024] if message.content else "*No text content*",
            inline=False
        )
        
        # Add context information
        if context:
            context_preview = "\n".join([
                f"• **{ctx['user_name']}**: {ctx['content'][:50]}..."
                for ctx in context[-3:]
            ])
            embed.add_field(
                name=f"Context ({len(context)} messages)",
                value=context_preview[:1024],
                inline=False
            )
        
        # Add placeholder notice
        embed.add_field(
            name="Status",
            value="🔄 Translation engine will be integrated in Task 4\n"
                  "Context has been retrieved and filtered (placeholder).",
            inline=False
        )
        
        # Add footer with requester info
        if requesting_user:
            embed.set_footer(text=f"Requested by {requesting_user.display_name}")
        
        # Send the response
        await channel.send(embed=embed)
        print(f"[Bot] Sent translation response for message {message.id}")


# Create bot instance
bot = AITranslatorBot()


# Simple ping command for health check
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    """Check if the bot is alive."""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: {latency}ms")


@bot.command(name="stats")
async def stats(ctx: commands.Context):
    """Show bot statistics."""
    embed = discord.Embed(
        title="📊 Bot Statistics",
        color=0x2ecc71
    )
    embed.add_field(name="Guilds", value=len(bot.guilds), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Translation Emoji", value=TRANSLATION_EMOJI, inline=True)
    await ctx.send(embed=embed)


def main():
    """Main entry point for the bot."""
    if not DISCORD_TOKEN:
        print("[Bot] Error: DISCORD_TOKEN environment variable is not set!")
        print("[Bot] Please set the DISCORD_TOKEN in your .env file")
        exit(1)
    
    print("[Bot] Starting AI Translator Bot...")
    print(f"[Bot] Translation trigger: {TRANSLATION_EMOJI} reaction")
    
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("[Bot] Error: Invalid Discord token!")
        exit(1)
    except Exception as e:
        print(f"[Bot] Fatal error: {e}")
        exit(1)
    finally:
        # Close database connection
        db.close()
        print("[Bot] Database connection closed")


if __name__ == "__main__":
    main()
