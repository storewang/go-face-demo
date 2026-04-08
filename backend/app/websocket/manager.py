from fastapi import WebSocket
from typing import Dict, Set


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.session_data: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.session_data[websocket] = {
            "frames": [],
            "face_locations": [],
            "last_result_time": 0,
            # 设备绑定字段
            "device_id": None,
            "device_code": None,
            "device_name": None,
        }

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.session_data.pop(websocket, None)

    async def send_json(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

    def get_session(self, websocket: WebSocket) -> dict:
        return self.session_data.get(websocket, {})

    def update_session(self, websocket: WebSocket, data: dict):
        if websocket in self.session_data:
            self.session_data[websocket].update(data)


manager = ConnectionManager()
