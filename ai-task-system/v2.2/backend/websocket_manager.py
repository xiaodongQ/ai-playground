import uuid
from fastapi import WebSocket
from typing import List, Dict, Optional
import asyncio

class WebSocketManager:
    def __init__(self):
        # Maps session_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Maps old_client_id -> new_client_id for reconnects
        self._reconnect_map: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None):
        """Connect a client. If client_id is provided and was previously connected,
        notify the system of reconnection. Always generates a new session_id."""
        await websocket.accept()
        async with self._lock:
            # Generate a session ID for this connection
            session_id = str(uuid.uuid4())
            self.active_connections[session_id] = websocket

            if client_id and client_id in self.active_connections:
                # This is a reconnection - mark old session as replaced
                self._reconnect_map[client_id] = session_id
                old_ws = self.active_connections.pop(client_id, None)
                if old_ws:
                    try:
                        await old_ws.close()
                    except Exception:
                        pass

            # Send the assigned session_id to the client
            try:
                await websocket.send_json({"type": "session_assigned", "session_id": session_id})
            except Exception:
                pass

        return session_id

    def disconnect(self, websocket: WebSocket):
        """Disconnect by finding and removing the websocket."""
        to_remove = None
        for sid, ws in self.active_connections.items():
            if ws == websocket:
                to_remove = sid
                break
        if to_remove:
            del self.active_connections[to_remove]

    async def broadcast(self, message: dict):
        for ws in list(self.active_connections.values()):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def send_to(self, session_id: str, message: dict):
        """Send message to a specific session."""
        async with self._lock:
            ws = self.active_connections.get(session_id)
            if ws:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    def get_session_id(self, websocket: WebSocket) -> Optional[str]:
        for sid, ws in self.active_connections.items():
            if ws == websocket:
                return sid
        return None
