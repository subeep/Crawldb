"""WebSocket endpoint for real-time crawl event streaming."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("crawldb.websocket")

router = APIRouter()

# Connected WebSocket clients
_clients: set[WebSocket] = set()
# Event queue for broadcasting
_event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)


async def broadcast_event(event_data: dict) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    if not _clients:
        return

    message = json.dumps(event_data, default=str)
    disconnected = set()

    for client in _clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)

    _clients -= disconnected


async def push_event(event_type: str, url: str, detail: str = "") -> None:
    """Push a crawl event to the broadcast queue."""
    from datetime import datetime
    event = {
        "event_type": event_type,
        "url": url,
        "detail": detail,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        _event_queue.put_nowait(event)
    except asyncio.QueueFull:
        pass  # Drop events when queue is full


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time crawl event streaming.

    Clients connect here to receive live updates about:
    - Pages being crawled
    - Duplicate detections
    - Errors encountered
    - Queue status changes
    """
    await websocket.accept()
    _clients.add(websocket)
    logger.info("WebSocket client connected (total: %d)", len(_clients))

    try:
        while True:
            # Keep connection alive, receive any client messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Client can send ping or commands
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
        logger.info("WebSocket client disconnected (total: %d)", len(_clients))
