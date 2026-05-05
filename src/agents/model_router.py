"""
OpenRouter-based model router for all extraction calls.

All models (Claude, GPT, Gemini) are accessed via the OpenRouter
OpenAI-compatible endpoint. No provider-specific SDKs needed.
"""

import asyncio
import logging
import time

import httpx
from openai import AsyncOpenAI

from src.config.settings import settings
from src.services.metering import record_llm_call

logger = logging.getLogger("mreit-monitor.model_router")


def _openrouter_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_headers={
            "HTTP-Referer": "https://hq.mmglobal.us",
            "X-Title": "Tom Bot mREIT Monitor",
        },
        timeout=httpx.Timeout(timeout=300.0, connect=10.0),
    )


async def _extract_with_local_model(
    system_prompt: str,
    user_content: str,
    max_tokens: int = 8192,
) -> tuple[str, dict]:
    """Route a text-only extraction to the local Ollama model (free)."""
    start = time.monotonic()
    client = AsyncOpenAI(
        api_key="ollama",
        base_url=settings.ollama_base_url,
        timeout=httpx.Timeout(timeout=float(settings.ollama_timeout_seconds), connect=5.0),
    )
    try:
        response = await client.chat.completions.create(
            model=settings.ollama_scraper_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"/no_think\n\n{user_content}"},
            ],
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        response_text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        logger.info("Ollama %s extraction: %dms", settings.ollama_scraper_model, elapsed_ms)
        asyncio.create_task(record_llm_call(
            provider="local",
            model=settings.ollama_scraper_model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            latency_ms=elapsed_ms,
            cost_usd_estimated=0.0,
            feature="reit_extraction",
        ))
        return response_text, {
            "model": settings.ollama_scraper_model,
            "provider": "local",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": elapsed_ms,
            "estimated_cost": 0.0,
        }
    except Exception as exc:
        logger.warning(
            "Ollama extraction failed (%s): %s — falling back to OpenRouter",
            settings.ollama_scraper_model, exc,
        )
        raise


async def extract_with_model(
    model: str,
    system_prompt: str,
    user_content: str | list,
    max_tokens: int = 8192,
) -> tuple[str, dict]:
    """
    Send an extraction request to OpenRouter (or local Ollama for text-only content).

    Handles both text-only and multimodal (PDF) content.
    For PDF content (list format with document blocks), converts to
    base64 image_url blocks which OpenRouter/Claude supports natively.

    When settings.local_extraction is True and content is text-only,
    routes to the local Ollama model instead of OpenRouter (free).

    Args:
        model: OpenRouter model ID e.g. "anthropic/claude-haiku-4.5"
        system_prompt: System prompt
        user_content: str for text, list for multimodal (Anthropic format)
        max_tokens: Max output tokens

    Returns:
        (response_text, metadata_dict)
    """
    if settings.local_extraction and isinstance(user_content, str):
        try:
            return await _extract_with_local_model(system_prompt, user_content, max_tokens)
        except Exception:
            logger.warning("Local extraction failed; falling back to OpenRouter model %s", model)

    start = time.monotonic()
    client = _openrouter_client()

    # Convert Anthropic multimodal format to OpenAI-compatible format
    if isinstance(user_content, list):
        openai_content: list = []
        for block in user_content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    openai_content.append({"type": "text", "text": block["text"]})
                elif block.get("type") == "document":
                    source = block.get("source", {})
                    if source.get("type") == "base64" and source.get("media_type") == "application/pdf":
                        openai_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:application/pdf;base64,{source['data']}"
                            },
                        })
                    else:
                        openai_content.append({"type": "text", "text": "[PDF document]"})
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": openai_content},
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    response_text = response.choices[0].message.content or ""
    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0

    logger.info(
        "OpenRouter %s: %d in / %d out / %dms",
        model, input_tokens, output_tokens, elapsed_ms,
    )

    asyncio.create_task(record_llm_call(
        provider="openrouter",
        model=model,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
        latency_ms=elapsed_ms,
        feature="reit_extraction",
    ))

    return response_text, {
        "model": model,
        "provider": "openrouter",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": elapsed_ms,
        "estimated_cost": 0.0,
    }


async def scrape_with_local_model(
    prompt: str,
    max_tokens: int = 4096,
) -> str:
    """
    Use local Ollama/Qwen3:4b for IR page scraping.
    Free — no API cost. Used only for finding document links on IR pages.

    Qwen3:4b requires /no_think to skip extended reasoning mode,
    otherwise it times out on longer prompts.
    """
    import time

    start = time.monotonic()
    client = AsyncOpenAI(
        api_key="ollama",
        base_url=settings.ollama_base_url,
        timeout=httpx.Timeout(timeout=float(settings.ollama_timeout_seconds), connect=5.0),
    )

    try:
        response = await client.chat.completions.create(
            model=settings.ollama_scraper_model,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "system",
                    "content": "You are a document link extractor. Return only valid JSON arrays with no markdown, no commentary.",
                },
                # /no_think must be at the start of the user message for Ollama/Qwen3
                # to disable extended reasoning mode; putting it in the system message alone
                # does not reliably suppress the thinking chain.
                {"role": "user", "content": f"/no_think\n\n{prompt}"},
            ],
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        response_text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        logger.info("Ollama %s scraper: %dms", settings.ollama_scraper_model, elapsed_ms)
        asyncio.create_task(record_llm_call(
            provider="local",
            model=settings.ollama_scraper_model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            latency_ms=elapsed_ms,
            cost_usd_estimated=0.0,
            feature="reit_ir_scrape",
        ))
        return response_text
    except Exception as exc:
        logger.error(
            "Ollama scraper failed (%s): %s — falling back to empty result",
            settings.ollama_scraper_model, exc,
        )
        return "[]"
