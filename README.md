# Discord AI Translator (for Humans) 🌐

A smart, context-aware Discord translation bot powered by **MiMo-V2-Flash (Feb 2026)**.

## Features
- **🌐 Reaction Trigger**: Simply react to any message with a globe emoji to translate it.
- **Smart Context**: Unlike basic translators, this bot looks at recent messages in the same channel/thread to understand the conversation flow before translating.
- **Topic Filtering**: Automatically filters out irrelevant side-chatter from the context to ensure high translation accuracy.
- **Enhanced Output**: Provides more than just text. You get:
  - **[Translation]**: The core translated message.
  - **[Context/Terms]**: Explanations of slang, idioms, or technical terms.
  - **[Tone Analysis]**: Insights into the speaker's original mood or intent.
- **Persistent Memory**: Uses SQLite to keep track of message history even after restarts.

## Setup
1. **Clone**: `git clone https://github.com/herointene/ai-translator-discord.git`
2. **Config**: Fill in `.env` with your `DISCORD_TOKEN` and `MIMO_API_KEY`.
3. **Deploy**: Run `docker-compose up -d`.

---

# AI-TRANSLATOR-DISCORD (for Agents) 🤖

**Project Nature**: Discord Gateway Listener (Python) + LLM Integration.

## Technical Specs
- **Runtime**: Python 3.12 (Asynchronous via `discord.py`).
- **Engine**: MiMo-V2-Flash API (Base URL configurable via ENV).
- **Data Layer**: SQLite3 with thread-local connections.
- **Persistence**: Mounted via Docker volumes at `/app/data/`.
- **Logic Flow**:
  1. `on_message` -> Save to DB.
  2. `on_raw_reaction_add` (🌐) -> Trigger.
  3. `translator.filter_context_with_ai` -> Semantic pruning of 10-message window.
  4. `translator.translate_with_context` -> Structured LLM prompt with tone & term extraction.
  5. `bot.py` -> Send Discord Embed.

## Critical Paths
- **Context Management**: `database.py` handles thread/channel isolation.
- **Instruction Override**: AI is instructed to prioritize language requests found at the start of message strings (e.g., "Translate to Japanese: ...").
- **Error Handling**: Graceful fallback to raw translation if context filtering fails.

## Deployment Strategy
Standard `docker-compose` orchestration. Ensure `known_hosts` is handled externally if deploying on read-only environments like starsoup.
