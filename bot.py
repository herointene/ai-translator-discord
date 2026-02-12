"""
Discord AI Translator - Bot Module

Core Discord bot implementation using discord.py.

Features:
- Saves all messages to SQLite database for context
- Listens for 🌐 reaction to trigger translation
- Retrieves relevant context from database
- AI-powered topic filtering and enhanced translation
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands

from database import db, save_message, get_relevant_context, get_message
from translator import translate_with_context, TranslationError


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
        3. Apply AI-based topic filtering
        4. Call translation API with enhanced output
        5. Send formatted translation response
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
            
            # Step 2: Apply AI-based topic filtering and translation
            translation_result = await translate_with_context(
                message.content,
                raw_context
            )
            
            # Step 3: Send the enhanced translation response
            await self._send_translation_response(
                channel, 
                message, 
                translation_result, 
                user
            )
            
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
        Filter context messages using AI semantic analysis.
        
        This method calls the translator module's AI-based filtering
        to identify semantically relevant context messages.
        
        Args:
            target_content: The message content to translate
            raw_context: List of raw context messages from database
            
        Returns:
            Filtered list of relevant context messages
        """
        from translator import filter_context_with_ai
        
        print(f"[TopicFilter] Filtering {len(raw_context)} messages for relevance...")
        print(f"[TopicFilter] Target message: {target_content[:100]}...")
        
        filtered = await filter_context_with_ai(target_content, raw_context)
        
        print(f"[TopicFilter] Retained {len(filtered)} relevant messages")
        if filtered:
            print(f"[TopicFilter] Relevant context:")
            for ctx in filtered:
                print(f"  - {ctx['user_name']}: {ctx['content'][:50]}...")
        
        return filtered
    
    async def _send_translation_response(
        self,
        channel: discord.TextChannel,
        message: discord.Message,
        translation_result: Dict[str, Any],
        requesting_user: Optional[discord.User]
    ):
        """
        Send enhanced translation response to the channel.
        
        Displays the translation with context explanation and tone analysis.
        """
        # Check for errors
        if translation_result.get("error"):
            error_embed = discord.Embed(
                title="❌ Translation Error",
                description=f"Failed to translate message: {translation_result['error']}",
                color=0xe74c3c,
                timestamp=datetime.now()
            )
            error_embed.add_field(
                name="Original Message",
                value=message.content[:1024] if message.content else "*No text content*",
                inline=False
            )
            await channel.send(embed=error_embed)
            return
        
        # Create the main translation embed
        embed = discord.Embed(
            title="🌐 Translation",
            color=0x3498db,
            timestamp=datetime.now()
        )
        
        # Add original message info
        embed.add_field(
            name=f"💬 Original ({message.author.display_name})",
            value=translation_result["original"][:1024] if translation_result["original"] else "*No text content*",
            inline=False
        )
        
        # Add translation
        translation_text = translation_result["translation"]
        if translation_text:
            # Discord embed field limit is 1024 chars
            if len(translation_text) > 1024:
                translation_text = translation_text[:1021] + "..."
            embed.add_field(
                name="📝 Translation",
                value=translation_text,
                inline=False
            )
        
        # Add context/term explanation if available and not empty/"None"
        context_exp = translation_result.get("context_explanation", "").strip()
        if context_exp and context_exp.lower() not in ["none", "n/a", "-", "无"]:
            if len(context_exp) > 1024:
                context_exp = context_exp[:1021] + "..."
            embed.add_field(
                name="📚 Context / Term Explanation",
                value=context_exp,
                inline=False
            )
        
        # Add tone notes if available and not empty/"None"
        tone_notes = translation_result.get("tone_notes", "").strip()
        if tone_notes and tone_notes.lower() not in ["none", "n/a", "-", "无"]:
            if len(tone_notes) > 1024:
                tone_notes = tone_notes[:1021] + "..."
            embed.add_field(
                name="🎭 Tone Notes",
                value=tone_notes,
                inline=False
            )
        
        # Add context info footer
        relevant_ctx = translation_result.get("relevant_context", [])
        if relevant_ctx:
            ctx_preview = ", ".join([ctx['user_name'] for ctx in relevant_ctx[-3:]])
            embed.set_footer(
                text=f"Requested by {requesting_user.display_name if requesting_user else 'Unknown'} • "
                     f"Used {len(relevant_ctx)} context messages ({ctx_preview})"
            )
        else:
            embed.set_footer(
                text=f"Requested by {requesting_user.display_name if requesting_user else 'Unknown'}"
            )
        
        # Send the response
        await channel.send(embed=embed)
        print(f"[Bot] Sent enhanced translation for message {message.id}")


# Create bot instance
bot = AITranslatorBot()


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


@bot.command(name="translate")
async def translate_command(ctx: commands.Context, *, text: str):
    """
    Translate text directly via command.
    
    Usage: !translate <text>
    Or: !translate 翻译为日语: <text>
    """
    async with ctx.typing():
        # Get recent context from the channel
        from database import get_recent_messages
        recent_msgs = get_recent_messages(
            channel_id=str(ctx.channel.id),
            limit=5
        )
        
        # Filter out the command message itself if present
        context = [
            msg for msg in recent_msgs 
            if msg['msg_id'] != str(ctx.message.id)
        ]
        
        # Perform translation
        result = await translate_with_context(text, context)
        
        if result.get("error"):
            await ctx.send(f"❌ Translation failed: {result['error']}")
            return
        
        # Create response embed
        embed = discord.Embed(
            title="🌐 Translation",
            color=0x3498db,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="💬 Original",
            value=result["original"][:1024],
            inline=False
        )
        
        if result["translation"]:
            embed.add_field(
                name="📝 Translation",
                value=result["translation"][:1024],
                inline=False
            )
        
        context_exp = result.get("context_explanation", "").strip()
        if context_exp and context_exp.lower() not in ["none", "n/a", "-", "无"]:
            embed.add_field(
                name="📚 Context / Term Explanation",
                value=context_exp[:1024],
                inline=False
            )
        
        tone_notes = result.get("tone_notes", "").strip()
        if tone_notes and tone_notes.lower() not in ["none", "n/a", "-", "无"]:
            embed.add_field(
                name="🎭 Tone Notes",
                value=tone_notes[:1024],
                inline=False
            )
        
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
