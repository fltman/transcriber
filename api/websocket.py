import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import settings
from ws_manager import manager

router = APIRouter()


@router.websocket("/ws/meetings/{meeting_id}")
async def meeting_websocket(websocket: WebSocket, meeting_id: str):
    await manager.connect(meeting_id, websocket)

    # Subscribe to Redis pub/sub for this meeting
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"meeting:{meeting_id}")

    try:
        # Forward Redis messages to WebSocket
        async def relay():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await websocket.send_json(data)

        relay_task = asyncio.create_task(relay())

        # Keep connection alive, listen for client messages
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                # Send ping to keep alive
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        relay_task.cancel()
        try:
            await pubsub.unsubscribe(f"meeting:{meeting_id}")
            await pubsub.close()
        except Exception:
            pass
        try:
            await r.aclose()
        except Exception:
            pass
        manager.disconnect(meeting_id, websocket)
