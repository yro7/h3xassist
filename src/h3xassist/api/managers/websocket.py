"""WebSocket connection manager for real-time updates."""

import asyncio
import logging
from typing import TYPE_CHECKING

from h3xassist.models.api import RefreshSignal

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts updates."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

        self._signal_tasks: set[asyncio.Task[None]] = set()

    async def connect(self, websocket: "WebSocket") -> None:
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug("WebSocket client connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: "WebSocket") -> None:
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.debug("WebSocket client disconnected. Total: %d", len(self.active_connections))

    async def broadcast_message(self, message: str) -> None:
        """Broadcast message to all connected WebSockets."""
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning("Failed to broadcast to connection: %s", e)
                disconnected.append(connection)

        # Clean up disconnected sockets
        for connection in disconnected:
            self.disconnect(connection)

    async def send_refresh_signal(self) -> None:
        """Send refresh signal to all connected clients."""
        signal = RefreshSignal()
        message = signal.model_dump_json()
        await self.broadcast_message(message)
        logger.debug("Sent refresh signal")

    def send_refresh_signal_sync(self) -> None:
        """Sync version of send_refresh_signal."""
        task = asyncio.create_task(self.send_refresh_signal())
        self._signal_tasks.add(task)
        task.add_done_callback(self._signal_tasks.discard)

    async def cleanup(self) -> None:
        """Clean up all connections."""
        for connection in self.active_connections.copy():
            try:
                await connection.close()
            except Exception as e:
                logger.warning("Error closing WebSocket: %s", e)

        self.active_connections.clear()
        logger.debug("All WebSocket connections cleaned up")
