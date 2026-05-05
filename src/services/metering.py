import logging

import httpx

logger = logging.getLogger("mreit-monitor.metering")


async def record_llm_call(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int = 0,
    status: str = "success",
    feature: str | None = None,
    cost_usd_estimated: float | None = None,
    error_message: str | None = None,
) -> None:
    """Fire-and-forget POST to a gateway /usage/record endpoint. Never raises.

    Set GATEWAY_URL in .env to enable. Silently skipped if not configured.
    """
    from src.config.settings import settings

    gateway_url = settings.gateway_url.rstrip("/")
    if not gateway_url:
        return

    payload = {
        "service": "reit_monitor",
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "latency_ms": latency_ms,
        "status": status,
        "feature": feature,
        "cost_usd_estimated": cost_usd_estimated,
        "error_message": error_message,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            await client.post(f"{gateway_url}/usage/record", json=payload)
    except Exception as exc:
        logger.warning("metering POST failed (non-fatal): %s", exc)
