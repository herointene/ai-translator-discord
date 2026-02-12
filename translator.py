"""
Discord AI Translator - Translation Module

Handles AI-powered translation using MiMo-V2-Flash API with:
- Smart context filtering using AI semantic analysis
- Language instruction detection (e.g., "翻译为日语")
- Enhanced translation output with context explanation and tone notes
"""

import os
import re
import json
from typing import List, Dict, Any, Optional, Tuple
import httpx


# Configuration from environment variables
MIMO_API_KEY = os.getenv("MIMO_API_KEY")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")

# Default model
DEFAULT_MODEL = os.getenv("MIMO_MODEL", "xiaomi/mimo-v2-flash")

# Language instruction patterns
LANGUAGE_PATTERNS = [
    # Chinese patterns
    (r"^翻译为?(\w+)", "auto"),
    (r"^翻译成?(\w+)", "auto"),
    (r"^译为?(\w+)", "auto"),
    (r"^译成?(\w+)", "auto"),
    # English patterns
    (r"^translate to (\w+)", "auto"),
    (r"^translate into (\w+)", "auto"),
]

# Language name mappings
LANGUAGE_MAP = {
    # Chinese names
    "中文": "zh",
    "简体中文": "zh",
    "繁体中文": "zh-tw",
    "英文": "en",
    "英语": "en",
    "日文": "ja",
    "日语": "ja",
    "韩文": "ko",
    "韩语": "ko",
    "法文": "fr",
    "法语": "fr",
    "德文": "de",
    "德语": "de",
    "西班牙文": "es",
    "西班牙语": "es",
    "俄文": "ru",
    "俄语": "ru",
    "意大利文": "it",
    "意大利语": "it",
    "葡萄牙文": "pt",
    "葡萄牙语": "pt",
    "阿拉伯文": "ar",
    "阿拉伯语": "ar",
    # English names
    "chinese": "zh",
    "simplified chinese": "zh",
    "traditional chinese": "zh-tw",
    "english": "en",
    "japanese": "ja",
    "korean": "ko",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "russian": "ru",
    "italian": "it",
    "portuguese": "pt",
    "arabic": "ar",
}


class TranslationError(Exception):
    """Custom exception for translation errors."""
    pass


def detect_language_instruction(content: str) -> Tuple[str, Optional[str]]:
    """
    Detect if the message starts with a language instruction.
    
    Args:
        content: The message content to analyze
        
    Returns:
        Tuple of (cleaned_content, target_language_code)
        target_language_code is None if no instruction detected
    """
    content = content.strip()
    
    for pattern, _ in LANGUAGE_PATTERNS:
        match = re.match(pattern, content, re.IGNORECASE)
        if match:
            lang_name = match.group(1).strip().lower()
            target_lang = LANGUAGE_MAP.get(lang_name)
            
            # Remove the instruction from content
            cleaned_content = content[match.end():].strip()
            # Also remove common delimiters like : or ：
            cleaned_content = re.sub(r"^[：:]\s*", "", cleaned_content)
            
            return cleaned_content, target_lang
    
    return content, None


def build_context_filter_prompt(
    target_content: str,
    context_list: List[Dict[str, Any]]
) -> str:
    """
    Build the prompt for AI-based context filtering.
    
    Args:
        target_content: The message to be translated
        context_list: List of context messages
        
    Returns:
        The prompt string for the AI
    """
    context_text = "\n".join([
        f"[{i+1}] {ctx['user_name']}: {ctx['content']}"
        for i, ctx in enumerate(context_list)
    ])
    
    prompt = f"""You are a context filtering assistant for a translation system.

Your task is to analyze a list of conversation messages and identify which ones are semantically relevant to the target message that needs translation.

Target message to translate:
"{target_content}"

Conversation context (most recent first):
{context_text}

Instructions:
1. Analyze the semantic relationship between the target message and each context message
2. Identify messages that share the same topic, refer to the same subject, or provide necessary context for understanding the target message
3. Return ONLY a JSON array of indices (1-based) of the relevant messages
4. If no messages are relevant, return an empty array []
5. Be selective - only include messages that truly add context value

Response format (JSON only):
[1, 3, 5]  // Example: messages 1, 3, and 5 are relevant

Your response:"""
    
    return prompt


def build_translation_prompt(
    message_content: str,
    filtered_context: List[Dict[str, Any]],
    target_language: Optional[str] = None
) -> str:
    """
    Build the enhanced translation prompt.
    
    Args:
        message_content: The message to translate
        filtered_context: Filtered list of relevant context messages
        target_language: Target language code (e.g., 'ja', 'en')
        
    Returns:
        The prompt string for the AI
    """
    # Build context section
    if filtered_context:
        context_text = "\n".join([
            f"- {ctx['user_name']}: {ctx['content']}"
            for ctx in filtered_context
        ])
        context_section = f"""
Relevant conversation context:
{context_text}
"""
    else:
        context_section = ""
    
    # Language instruction
    if target_language:
        lang_names = {
            "zh": "Chinese (Simplified)",
            "zh-tw": "Chinese (Traditional)",
            "en": "English",
            "ja": "Japanese",
            "ko": "Korean",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "ru": "Russian",
            "it": "Italian",
            "pt": "Portuguese",
            "ar": "Arabic",
        }
        lang_name = lang_names.get(target_language, target_language)
        lang_instruction = f"Translate the following message into {lang_name}."
    else:
        lang_instruction = "Detect the source language and translate into English (or keep as English if already in English)."
    
    prompt = f"""You are an expert translator with deep cultural and linguistic knowledge.

{lang_instruction}

Message to translate:
"{message_content}"
{context_section}
Provide an enhanced translation with the following sections:

[Translation]
Provide the direct translation here. Maintain the original formatting (line breaks, emojis, etc.).

[Context/Term Explanation]
If the message contains:
- Cultural references
- Idioms or slang
- Technical terms
- Names or proper nouns
- References to previous conversation topics
Explain them briefly here. If nothing needs explanation, write "None".

[Tone Notes]
Analyze and describe:
- The overall tone (formal, casual, humorous, serious, sarcastic, etc.)
- Any emotional subtext
- Register (polite, friendly, professional, etc.)
- Any nuances that might be lost in translation

Format your response exactly with these section headers in brackets."""
    
    return prompt


async def call_mimo_api(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 2000
) -> str:
    """
    Call the MiMo-V2-Flash API.
    
    Args:
        prompt: The prompt to send
        model: Model name to use
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        
    Returns:
        The API response text
        
    Raises:
        TranslationError: If the API call fails
    """
    if not MIMO_API_KEY:
        raise TranslationError("MIMO_API_KEY environment variable is not set")
    
    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{MIMO_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise TranslationError(
                    f"API returned status {response.status_code}: {response.text}"
                )
            
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                raise TranslationError("Invalid API response: no choices found")
            
            return data["choices"][0]["message"]["content"]
            
    except httpx.TimeoutException:
        raise TranslationError("API request timed out")
    except httpx.RequestError as e:
        raise TranslationError(f"API request failed: {e}")
    except json.JSONDecodeError:
        raise TranslationError("Invalid JSON response from API")


async def filter_context_with_ai(
    target_content: str,
    context_list: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Use AI to filter context messages for semantic relevance.
    
    Args:
        target_content: The message to be translated
        context_list: List of raw context messages
        
    Returns:
        Filtered list of relevant context messages
    """
    if not context_list:
        return []
    
    # If there's only one or two messages, return all of them
    if len(context_list) <= 2:
        return context_list
    
    try:
        prompt = build_context_filter_prompt(target_content, context_list)
        response = await call_mimo_api(
            prompt,
            temperature=0.1,  # Low temperature for consistent filtering
            max_tokens=500
        )
        
        # Parse the JSON response
        # Clean up the response to extract just the JSON array
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\s*", "", response)
            response = re.sub(r"\s*```$", "", response)
        
        # Try to find a JSON array in the response
        match = re.search(r"\[[\d,\s]*\]", response)
        if match:
            response = match.group(0)
        
        relevant_indices = json.loads(response)
        
        if not isinstance(relevant_indices, list):
            print(f"[Translator] Invalid response format, expected list: {response}")
            return context_list
        
        # Convert 1-based indices to 0-based and filter
        filtered = []
        for idx in relevant_indices:
            if isinstance(idx, int) and 1 <= idx <= len(context_list):
                filtered.append(context_list[idx - 1])
        
        print(f"[Translator] Filtered {len(context_list)} messages to {len(filtered)} relevant")
        return filtered if filtered else context_list
        
    except json.JSONDecodeError as e:
        print(f"[Translator] Failed to parse context filter response: {e}")
        return context_list
    except Exception as e:
        print(f"[Translator] Context filtering failed: {e}")
        return context_list


async def translate_with_context(
    message_content: str,
    context_list: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Main translation function with enhanced output.
    
    This function:
    1. Uses AI to filter context_list for semantically relevant messages
    2. Detects if message starts with a language instruction
    3. Performs enhanced translation with context explanation and tone notes
    
    Args:
        message_content: The message content to translate
        context_list: List of recent context messages from database
        
    Returns:
        Dictionary containing:
        - original: Original message content
        - cleaned: Message with language instruction removed
        - target_language: Detected target language code (or None)
        - translation: The translated text
        - context_explanation: Explanation of terms/context
        - tone_notes: Analysis of tone and register
        - relevant_context: The filtered context messages used
        - error: Error message if translation failed
    """
    result = {
        "original": message_content,
        "cleaned": message_content,
        "target_language": None,
        "translation": "",
        "context_explanation": "",
        "tone_notes": "",
        "relevant_context": [],
        "error": None
    }
    
    try:
        # Step 1: Filter context using AI
        print(f"[Translator] Filtering {len(context_list)} context messages...")
        filtered_context = await filter_context_with_ai(message_content, context_list)
        result["relevant_context"] = filtered_context
        
        # Step 2: Detect language instruction
        cleaned_content, target_lang = detect_language_instruction(message_content)
        result["cleaned"] = cleaned_content
        result["target_language"] = target_lang
        
        # Step 3: Build and send translation prompt
        prompt = build_translation_prompt(cleaned_content, filtered_context, target_lang)
        print(f"[Translator] Sending translation request...")
        
        response = await call_mimo_api(prompt, temperature=0.3, max_tokens=2000)
        
        # Step 4: Parse the enhanced translation response
        parsed = parse_translation_response(response)
        result["translation"] = parsed.get("translation", "")
        result["context_explanation"] = parsed.get("context_explanation", "")
        result["tone_notes"] = parsed.get("tone_notes", "")
        
        print(f"[Translator] Translation completed successfully")
        
    except TranslationError as e:
        print(f"[Translator] Translation error: {e}")
        result["error"] = str(e)
    except Exception as e:
        print(f"[Translator] Unexpected error: {e}")
        result["error"] = f"Unexpected error: {e}"
    
    return result


def parse_translation_response(response: str) -> Dict[str, str]:
    """
    Parse the enhanced translation response into sections.
    
    Args:
        response: The raw API response
        
    Returns:
        Dictionary with translation, context_explanation, and tone_notes
    """
    result = {
        "translation": "",
        "context_explanation": "",
        "tone_notes": ""
    }
    
    # Define section markers
    sections = {
        "translation": ["[Translation]", "【Translation】", "Translation:"],
        "context_explanation": ["[Context/Term Explanation]", "【Context/Term Explanation】", "Context/Term Explanation:", "[Context]", "【Context】"],
        "tone_notes": ["[Tone Notes]", "【Tone Notes】", "Tone Notes:", "[Tone]", "【Tone】"]
    }
    
    # Find all section positions
    section_positions = []
    for section_name, markers in sections.items():
        for marker in markers:
            pos = response.find(marker)
            if pos != -1:
                section_positions.append((pos, section_name, len(marker)))
                break
    
    # Sort by position
    section_positions.sort(key=lambda x: x[0])
    
    # Extract content between sections
    for i, (pos, name, marker_len) in enumerate(section_positions):
        start = pos + marker_len
        if i + 1 < len(section_positions):
            end = section_positions[i + 1][0]
        else:
            end = len(response)
        
        content = response[start:end].strip()
        # Remove leading colon or whitespace
        content = re.sub(r"^[：:]\s*", "", content)
        result[name] = content
    
    # If no sections were found, treat entire response as translation
    if not result["translation"]:
        result["translation"] = response.strip()
    
    return result


# Convenience function for direct use
async def translate(
    content: str,
    context: Optional[List[Dict[str, Any]]] = None,
    target_lang: Optional[str] = None
) -> Dict[str, Any]:
    """
    Simple translation function.
    
    Args:
        content: Content to translate
        context: Optional context messages
        target_lang: Optional target language override
        
    Returns:
        Translation result dictionary
    """
    context = context or []
    
    # If target_lang is provided, prepend it to content temporarily
    # so detect_language_instruction can pick it up
    if target_lang:
        lang_names_reverse = {v: k for k, v in LANGUAGE_MAP.items()}
        lang_name = lang_names_reverse.get(target_lang, target_lang)
        content = f"翻译为{lang_name}：{content}"
    
    return await translate_with_context(content, context)
