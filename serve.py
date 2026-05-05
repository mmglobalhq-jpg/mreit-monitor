"""
Entry point for TomBot.REITMonitorSvc.

Sets WindowsSelectorEventLoopPolicy before any asyncio import — required on
Windows for compatibility with uvicorn and async libraries.
"""
import asyncio

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402

from src.config.settings import settings  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
