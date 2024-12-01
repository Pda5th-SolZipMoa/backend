from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.websockets import manager

# 라우터 생성
router = APIRouter()

# WebSocket 엔드포인트
@router.websocket("/{property_id}")
async def websocket_endpoint(websocket: WebSocket, property_id: int):
    await manager.connect(websocket, property_id)
    try:
        while True:
            data = await websocket.receive_text()  # WebSocket 연결 유지
            print(f"Received WebSocket message from client: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, property_id)
    except Exception as e:
        print(f"WebSocket error: {e}")