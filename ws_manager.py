import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, meeting_id: str, ws: WebSocket):
        await ws.accept()
        if meeting_id not in self.active:
            self.active[meeting_id] = []
        self.active[meeting_id].append(ws)

    def disconnect(self, meeting_id: str, ws: WebSocket):
        if meeting_id in self.active:
            self.active[meeting_id] = [
                w for w in self.active[meeting_id] if w != ws
            ]

    async def broadcast(self, meeting_id: str, data: dict):
        if meeting_id not in self.active:
            return
        dead = []
        for ws in self.active[meeting_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active[meeting_id].remove(ws)


manager = ConnectionManager()
