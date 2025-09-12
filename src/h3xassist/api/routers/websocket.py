"""WebSocket API router."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from h3xassist.api.dependencies import ConnectionManagerDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, manager: ConnectionManagerDep) -> None:
    """WebSocket endpoint for real-time communication."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
            logger.debug("Received WebSocket message: %s", data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
