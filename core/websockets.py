from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, property_id: int):
        """WebSocket 연결을 수립."""
        await websocket.accept()
        if property_id not in self.active_connections:
            self.active_connections[property_id] = []
        self.active_connections[property_id].append(websocket)
        print(f"WebSocket 연결 성공: property_id={property_id}")

    def disconnect(self, websocket: WebSocket, property_id: int):
        """WebSocket 연결을 종료."""
        if property_id in self.active_connections:
            self.active_connections[property_id].remove(websocket)
            if not self.active_connections[property_id]:
                del self.active_connections[property_id]
            print(f"WebSocket 연결 종료: property_id={property_id}")

    async def broadcast(self, message: str, property_id: int):
        """WebSocket 메시지를 연결된 클라이언트에 브로드캐스트."""
        if property_id in self.active_connections:
            print(f"Broadcasting message to {len(self.active_connections[property_id])} clients for property_id {property_id}")
            for connection in self.active_connections[property_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error sending message to WebSocket client: {e}")


# WebSocket 연결 관리 인스턴스 생성
manager = ConnectionManager()