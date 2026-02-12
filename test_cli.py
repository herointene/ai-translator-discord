import asyncio
import os
from translator import translate_with_context

async def test_translation(text, context=[]):
    print(f"\n--- Testing Input ---")
    print(f"Text: {text}")
    print(f"Context: {context}")
    print(f"--- Result ---")
    try:
        result = await translate_with_context(text, context)
        print(f"Translation: {result['translation']}")
        if result.get('explanation'):
            print(f"Explanation: {result['explanation']}")
        if result.get('tone_notes'):
            print(f"Tone: {result['tone_notes']}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    # Test case 1: Specific language instruction
    await test_translation("翻译成日文\n\n你好，今天天气不错。")
    
    # Test case 2: Default translation (should be English)
    await test_translation("这个项目进展得很快。")
    
    # Test case 3: Ambiguous context
    await test_translation("これ、いくらですか？")

if __name__ == "__main__":
    asyncio.run(main())
