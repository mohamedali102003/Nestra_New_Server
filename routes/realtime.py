# routes/realtime.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # بنخزن الاتصال مربوط بالإيميل: {'ahmed@test.com': websocket_obj}
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, email: str):
        await websocket.accept()
        self.active_connections[email] = websocket
        print(f"🔌 User connected: {email}")

    def disconnect(self, email: str):
        if email in self.active_connections:
            del self.active_connections[email]
            print(f"❌ User disconnected: {email}")

    async def send_personal_message(self, message: str, email: str):
        if email in self.active_connections:
            try:
                await self.active_connections[email].send_text(message)
            except Exception:
                self.disconnect(email)

manager = ConnectionManager()

@router.websocket("/ws/{email}")
async def websocket_endpoint(websocket: WebSocket, email: str):
    await manager.connect(websocket, email)
    try:
        while True:
            # Heartbeat: عشان الخط ما يفصلش
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(email)