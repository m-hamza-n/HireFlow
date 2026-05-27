import asyncio
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected: user {user_id}")

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        logger.info(f"WebSocket disconnected: user {user_id}")

    async def send_to_user(self, user_id: str, data: dict):
        """Send JSON data to a specific user if connected."""
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
                logger.debug(f"Sent notification to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send to user {user_id}: {e}")
                self.disconnect(user_id)

manager = ConnectionManager()