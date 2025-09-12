"""Service control endpoints for H3xAssist."""

import asyncio
import logging
import os
import signal
from datetime import UTC, datetime

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["service"])


@router.post("/service/restart")
async def restart_service() -> dict[str, str | int]:
    """Send SIGINT to self for systemd restart.

    This endpoint sends SIGINT signal to the current process,
    which will cause systemd to restart the service automatically.
    """
    pid = os.getpid()
    timestamp = datetime.now(UTC).isoformat()

    logger.info("Service restart requested via API (PID: %s)", pid)

    # Schedule SIGINT after response is sent
    _ = asyncio.create_task(_send_sigint_delayed())  # noqa: RUF006

    return {
        "status": "restart_initiated",
        "pid": pid,
        "timestamp": timestamp,
        "message": "SIGINT will be sent in 1 second",
    }


async def _send_sigint_delayed() -> None:
    """Send SIGINT to self after a short delay to allow response to be sent."""
    await asyncio.sleep(1.0)

    pid = os.getpid()
    logger.info("Sending SIGINT to self (PID: %s)", pid)

    try:
        os.kill(pid, signal.SIGINT)
    except Exception as e:
        logger.error("Failed to send SIGINT: %s", e)


@router.get("/service/status")
async def service_status() -> dict[str, str | int]:
    """Get basic service status information."""
    return {"status": "running", "pid": os.getpid(), "timestamp": datetime.now(UTC).isoformat()}
