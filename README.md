# Discord AI Translator (for Humans) 🌐

A smart, context-aware Discord translation bot powered by **MiMo-V2-Flash (Feb 2026)**.

## Features
- **Flag Emoji Translation (NEW)**: React with 🇨🇳 (Chinese), 🇯🇵 (Japanese), or 🇬🇧 (English) to force translate into a specific target language.
- **Thread-Based Interaction**: Keeps channels clean by moving translations into dedicated discussion threads.
- **Smart Context & Topic Filtering**: Analyzes recent messages to understand the conversation flow and filters out irrelevant chatter.
- **AI Task Recognition**: Automatically switches from translation to task fulfillment (e.g., writing emails, summarizing) based on user intent.
- **Resource Management**: Periodic database cleanup (TTL) and channel whitelisting support.

## Setup
1. **Clone**: `git clone https://github.com/herointene/ai-translator-discord.git`
2. **Config**: Fill in `.env` with:
   - `DISCORD_TOKEN`: Your bot token.
   - `MIMO_API_KEY`: MiMo-V2-Flash API key.
   - `ALLOWED_CHANNELS`: (Optional) Comma-separated channel IDs to restrict the bot.
3. **Deploy**: Run `docker compose up -d`.

---

# AI-TRANSLATOR-DISCORD (for Agents) 🤖

**Project Nature**: Discord Gateway Listener (Python) + LLM Task Processor.

## Technical Specs
- **Runtime**: Python 3.12 (Asynchronous `discord.py`).
- **Engine**: MiMo-V2-Flash (OpenAI-compatible).
- **Data Layer**: SQLite3 with 7-day TTL cleanup task.
- **Interaction Model**: `on_raw_reaction_add` (🌐, 🇨🇳, 🇯🇵, 🇬🇧) -> `message.create_thread` -> Task/Translation output.
- **Channel Restriction**: Controlled via `ALLOWED_CHANNELS` environment variable.
