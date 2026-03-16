"""
Multi-provider model router for extraction.

Routes extraction calls to Claude, OpenAI, or Gemini based on model name prefix:
  - claude-* → Anthropic SDK
  - gpt-* → OpenAI SDK
  - gemini-* → Google GenAI SDK

All providers return the same format: (parsed_json_dict, metadata_dict).
"""

import base64
import json
import logging
import time

from src.config.settings import settings

logger = logging.getLogger("mreit-monitor.model_router")

# Cost per 1M tokens (input, output) for supported models
MODEL_COSTS = {
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token counts."""
    costs = MODEL_COSTS.get(model, (3.00, 15.00))
    return (input_tokens * costs[0] + output_tokens * costs[1]) / 1_000_000


async def extract_with_model(
    model: str,
    system_prompt: str,
    user_content: str | list,
    max_tokens: int = 8192,
) -> tuple[str, dict]:
    """
    Send an extraction request to the appropriate provider.

    Args:
        model: Model name (e.g., "claude-sonnet-4-20250514", "gpt-4o-mini", "gemini-2.5-flash")
        system_prompt: System/instruction prompt
        user_content: User message (str for text, list for Anthropic multimodal)
        max_tokens: Maximum output tokens

    Returns:
        Tuple of (response_text, metadata_dict) where metadata includes
        model, input_tokens, output_tokens, estimated_cost, latency_ms
    """
    start = time.monotonic()

    if model.startswith("claude"):
        text, meta = await _extract_anthropic(model, system_prompt, user_content, max_tokens)
    elif model.startswith("gpt"):
        text, meta = await _extract_openai(model, system_prompt, user_content, max_tokens)
    elif model.startswith("gemini"):
        text, meta = await _extract_gemini(model, system_prompt, user_content, max_tokens)
    else:
        raise ValueError(f"Unknown model prefix: {model}")

    elapsed_ms = int((time.monotonic() - start) * 1000)
    meta["latency_ms"] = elapsed_ms
    meta["estimated_cost"] = estimate_cost(
        model, meta.get("input_tokens", 0), meta.get("output_tokens", 0)
    )

    return text, meta


async def _extract_anthropic(
    model: str,
    system_prompt: str,
    user_content: str | list,
    max_tokens: int,
) -> tuple[str, dict]:
    """Call Anthropic Claude API."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text

    return response_text, {
        "model": model,
        "provider": "anthropic",
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }


async def _extract_openai(
    model: str,
    system_prompt: str,
    user_content: str | list,
    max_tokens: int,
) -> tuple[str, dict]:
    """Call OpenAI API."""
    from openai import AsyncOpenAI

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Convert Anthropic multimodal format to text-only for OpenAI
    if isinstance(user_content, list):
        text_parts = []
        for block in user_content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block["text"])
            elif isinstance(block, dict) and block.get("type") == "document":
                text_parts.append("[PDF document attached — not supported for this model, using text extraction only]")
        user_text = "\n".join(text_parts)
    else:
        user_text = user_content

    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + "\n\nIMPORTANT: Return ONLY valid JSON."},
            {"role": "user", "content": user_text},
        ],
    )

    response_text = response.choices[0].message.content or ""

    return response_text, {
        "model": model,
        "provider": "openai",
        "input_tokens": response.usage.prompt_tokens if response.usage else 0,
        "output_tokens": response.usage.completion_tokens if response.usage else 0,
    }


async def _extract_gemini(
    model: str,
    system_prompt: str,
    user_content: str | list,
    max_tokens: int,
) -> tuple[str, dict]:
    """Call Google Gemini API."""
    from google import genai

    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    client = genai.Client(api_key=settings.gemini_api_key)

    # Convert Anthropic multimodal format to text-only for Gemini
    if isinstance(user_content, list):
        text_parts = []
        for block in user_content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block["text"])
            elif isinstance(block, dict) and block.get("type") == "document":
                text_parts.append("[PDF document attached — not supported for this model, using text extraction only]")
        user_text = "\n".join(text_parts)
    else:
        user_text = user_content

    # Map our model names to Gemini model IDs
    gemini_model_map = {
        "gemini-2.5-flash": "gemini-2.5-flash",
        "gemini-2.0-flash": "gemini-2.0-flash",
        "gemini-2.5-pro": "gemini-2.5-pro",
    }
    gemini_model = gemini_model_map.get(model, model)

    response = await client.aio.models.generate_content(
        model=gemini_model,
        contents=f"{system_prompt}\n\n---\n\n{user_text}",
        config={
            "response_mime_type": "application/json",
            "max_output_tokens": max_tokens,
        },
    )

    response_text = response.text or ""

    # Gemini doesn't always expose token counts in the same way
    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) if response.usage_metadata else 0
    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) if response.usage_metadata else 0

    return response_text, {
        "model": model,
        "provider": "google",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
