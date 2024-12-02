from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from uuid import uuid4

router = APIRouter()

# 댓글 데이터와 WebSocket 관리
comments = []
rooms: Dict[str, List[WebSocket]] = {}


class Comment(BaseModel):
    id: str
    room: str
    author: str
    content: str
    likes: int = 0
    is_liked: bool = False

# REST API: 특정 Room의 댓글 불러오기


@router.get("/comments/{room_id}")
async def get_comments(room_id: str):
    """특정 Room의 댓글 데이터 반환"""
    return [comment for comment in comments if comment['room'] == room_id]

# REST API: 댓글 추가


@router.post("/comments")
async def add_comment(comment: Comment):
    """새 댓글 추가"""
    comments.append(comment.dict())
    return comment

# REST API: 좋아요 토글


@router.patch("/comments/{comment_id}")
async def toggle_like(comment_id: str):
    """좋아요 토글"""
    for comment in comments:
        if comment["id"] == comment_id:
            comment["is_liked"] = not comment["is_liked"]
            comment["likes"] += 1 if comment["is_liked"] else -1
            return comment
    raise HTTPException(status_code=404, detail="Comment not found")

# REST API: 댓글 삭제


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str):
    """댓글 삭제"""
    global comments
    comments = [c for c in comments if c["id"] != comment_id]
    return {"success": True}

# WebSocket: 특정 Room에 연결


@router.websocket("/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """특정 Room에 WebSocket 연결"""
    await websocket.accept()
    if room_id not in rooms:
        rooms[room_id] = []
    rooms[room_id].append(websocket)

    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_json()
            new_comment = {
                "id": str(uuid4()),
                "room": room_id,
                "author": data["author"],
                "content": data["content"],
                "likes": 0,
                "is_liked": False,
            }
            comments.append(new_comment)

            # Room에 연결된 모든 클라이언트에 메시지 전송
            for connection in rooms[room_id]:
                await connection.send_json(new_comment)
    except WebSocketDisconnect:
        rooms[room_id].remove(websocket)
