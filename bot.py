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
FLAG_TO_LANG = {
    "🇨🇳": "zh",
    "🇯🇵": "ja",
    "🇬🇧": "en"
}
# Optional: restrict to specific channels (comma-separated IDs)
ALLOWED_CHANNELS = os.getenv("ALLOWED_CHANNELS", "").split(",")
ALLOWED_CHANNELS = [c.strip() for c in ALLOWED_CHANNELS if c.strip()]

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
        # Start cleanup task
        self.loop.create_task(self._periodic_cleanup())
        print("[Bot] AI Translator Bot is ready!")

    async def _periodic_cleanup(self):
        """Periodically delete old messages from database."""
        while not self.is_closed():
            try:
                # Cleanup every 24 hours, keep 7 days of history
                print("[Bot] Running database cleanup...")
                deleted = self.db.delete_old_messages(days=7)
                print(f"[Bot] Cleaned up {deleted} old messages")
            except Exception as e:
                print(f"[Bot] Error during cleanup: {e}")
            await asyncio.sleep(86400) # 24 hours
    
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
        
        # Check if channel is allowed
        if ALLOWED_CHANNELS and str(message.channel.id) not in ALLOWED_CHANNELS:
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
        Handle reaction add events - trigger translation on 🌐 or flag emojis.
        
        Uses raw reaction event to catch reactions on messages not in cache.
        """
        emoji_str = str(payload.emoji)
        print(f"[Debug] Reaction added: {emoji_str}")
        target_lang = None
        
        # Check if it's the default translation emoji
        if emoji_str == TRANSLATION_EMOJI:
            target_lang = None # Use auto-detection or default to English
        # Check if it's a flag emoji for specific language
        elif emoji_str in FLAG_TO_LANG:
            target_lang = FLAG_TO_LANG[emoji_str]
        else:
            return
        
        # Ignore bot's own reactions
        if payload.user_id == self.user.id:
            return
        
        print(f"[Bot] Translation triggered for message {payload.message_id} by user {payload.user_id} (Target: {target_lang or 'Auto'})")
        
        # Process translation request
        await self._handle_translation_request(payload, target_lang=target_lang)
    
    async def _handle_translation_request(self, payload: discord.RawReactionActionEvent, target_lang: Optional[str] = None):
        """
        Handle a translation request triggered by reaction.
        
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
            if not user:
                try:
                    user = await self.fetch_user(payload.user_id)
                except:
                    user = None
            
            user_name = user.display_name if user else f"User {payload.user_id}"
            
            print(f"[Bot] Translating message from {message.author.display_name} for {user_name} to {target_lang or 'Auto'}")
            
            # Show typing status to give user feedback
            async with channel.typing():
                # Step 1: Retrieve raw context from database
                raw_context = get_relevant_context(str(message.id), limit=10)
                print(f"[Bot] Retrieved {len(raw_context)} raw context messages")
                
                # Step 2: Apply AI-based topic filtering and translation
                translation_result = await translate_with_context(
                    message.content,
                    raw_context,
                    target_lang=target_lang
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
        Send translation response in a thread for cleaner interaction.
        """
        # Check for errors
        if translation_result.get("error"):
            await channel.send(f"❌ **Translation Error**: {translation_result['error']}", reference=message)
            return
        
        # Determine the response title and content
        # Note: 'translation' key might be renamed to 'response' for non-translation tasks in prompt
        is_task = "Response" in translation_result.get("translation", "") or \
                  "Response" in translation_result.get("original", "")
        
        title = "📄 **Task Response**" if is_task else "🌐 **Translation**"
        
        # Prepare content string
        # We move away from Embeds to avoid the 'quote block' look
        response_text = f"{title} (Original by {message.author.display_name})\n\n"
        
        translation_text = translation_result["translation"]
        if translation_text:
            response_text += f"{translation_text}\n"
        
        # Add context/term explanation only if significant
        context_exp = translation_result.get("context_explanation", "").strip()
        if context_exp and context_exp.lower() not in ["none", "n/a", "-", "无"]:
            response_text += f"\n**📚 Context / Term Explanation**\n{context_exp}\n"
        
        # Add tone notes only if significant
        tone_notes = translation_result.get("tone_notes", "").strip()
        if tone_notes and tone_notes.lower() not in ["none", "n/a", "-", "无"]:
            response_text += f"\n**🎭 Tone Notes**\n{tone_notes}\n"
        
        # Footer (Simplified, no longer using a heavy separator)
        response_text += f"\n\n*Requested by {requesting_user.display_name if requesting_user else 'Unknown'}*"
        
        # Send the response
        try:
            # Create a thread for the translation to keep channel clean and allow follow-ups
            # Limit thread name length
            safe_content = (message.content[:40] + '...') if len(message.content) > 40 else message.content
            thread_name = f"Translation: {safe_content}".replace("\n", " ")
            
            # If we are already in a thread, just send the message
            if isinstance(channel, discord.Thread):
                await channel.send(response_text)
            else:
                # Create a public thread attached to the original message
                thread = await message.create_thread(
                    name=thread_name,
                    auto_archive_duration=60 # Archive after 1 hour of inactivity
                )
                await thread.send(response_text)
        except Exception as thread_err:
            # Fallback to normal message with reference if thread creation fails (e.g. permission)
            print(f"[Bot] Thread creation failed, falling back: {thread_err}")
            await channel.send(response_text, reference=message)
            
        print(f"[Bot] Sent response for message {message.id}")


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
