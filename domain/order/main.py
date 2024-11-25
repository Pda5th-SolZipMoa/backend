from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from contextlib import asynccontextmanager
import pymysql
import redis
import asyncio
import json
import os
from pydantic import BaseModel
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# MySQL 설정
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "charset": os.getenv("DB_CHARSET"),
}

# Redis 설정
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    db=int(os.getenv("REDIS_DB")),
    decode_responses=True
)

# FastAPI 앱 생성
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup")
    loop = asyncio.get_event_loop()
    loop.create_task(redis_listener())
    yield
    print("Application shutdown")

app = FastAPI(lifespan=lifespan)


# WebSocket 연결 관리 클래스
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, property_id: int):
        await websocket.accept()
        if property_id not in self.active_connections:
            self.active_connections[property_id] = []
        self.active_connections[property_id].append(websocket)
        print(f"WebSocket 연결 성공: property_id={property_id}")

    def disconnect(self, websocket: WebSocket, property_id: int):
        if property_id in self.active_connections:
            self.active_connections[property_id].remove(websocket)
            if not self.active_connections[property_id]:
                del self.active_connections[property_id]
            print(f"WebSocket 연결 종료: property_id={property_id}")

    async def broadcast(self, message: str, property_id: int):
        if property_id in self.active_connections:
            print(f"Broadcasting message to {len(self.active_connections[property_id])} clients for property_id {property_id}")
            for connection in self.active_connections[property_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error sending message to WebSocket client: {e}")


# WebSocket 연결 관리 인스턴스 생성
manager = ConnectionManager()

@app.websocket("/api/ws/orders/{property_id}")
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


# Redis Pub/Sub Listener
async def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("order_book_updates")
    print("Redis listener started, subscribed to 'order_book_updates'")
    try:
        while True:
            message = pubsub.get_message()
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                property_id = data.get("property_id")
                print(f"Redis message received: {data}")
                if property_id:
                    await manager.broadcast(json.dumps(data), property_id)
            await asyncio.sleep(0.01)  # Redis 메시지 폴링 간격
    except Exception as e:
        print(f"Redis listener error: {e}")


# Redis 데이터 업데이트 및 Pub/Sub 메시지 발행
def update_order_book_in_redis(property_id: int, order_book: dict):
    redis_key = f"order_book:{property_id}"
    redis_client.hset(redis_key, "order_book", json.dumps(order_book))

    # Pub/Sub 메시지 발행
    update_message = {"property_id": property_id, "order_book": order_book}
    print(f"Publishing Redis message: {update_message}")
    redis_client.publish("order_book_updates", json.dumps(update_message))


# Pydantic 모델
class BuyOrderRequest(BaseModel):
    quantity: int
    price_per_token: int


class SellOrderRequest(BaseModel):
    quantity: int
    price_per_token: int


# 주문 제출 API (매수)
@app.post("/api/orders/{property_id}/buy")
async def submit_buy_order(order: BuyOrderRequest, property_id: int):
    # TODO: JWT에서 유저 ID 가져오기
    user_id = 1

    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()

        # TODO: 1. 사용자 잔액 확인
        user_balance = 10000000
        total_cost = order.quantity * order.price_per_token
        if user_balance < total_cost:
            raise HTTPException(status_code=400, detail="유저 잔액 부족")

        # 2. 주문 기록 저장 (Order_Archive 테이블)
        query = """
            INSERT INTO Order_Archive (property_id, user_id, order_type, price_per_token, quantity, remain, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (
            property_id, user_id, "buy", order.price_per_token, order.quantity, order.quantity, "normal"))
        conn.commit()

        order_id = cursor.lastrowid

        # 3. Redis 호가창 업데이트
        redis_key = f"order_book:{property_id}"
        existing_order_book = redis_client.hget(redis_key, "order_book")
        order_book = json.loads(existing_order_book) if existing_order_book else {"buy": {}, "sell": {}}
        if str(order.price_per_token) not in order_book["buy"]:
            order_book["buy"][str(order.price_per_token)] = []
        order_book["buy"][str(order.price_per_token)].append({"order_id": order_id, "quantity": order.quantity})

        update_order_book_in_redis(property_id, order_book)

    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    return {"message": "매수 주문이 완료", "order_id": order_id}


# 주문 제출 API (매도)
@app.post("/api/orders/{property_id}/sell")
async def submit_sell_order(order: SellOrderRequest, property_id: int):
    # TODO: JWT에서 유저 ID 가져오기
    user_id = 1

    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()

        # TODO: 1. 사용자의 보유 토큰 확인
        user_tokens = 10000000
        if user_tokens is None or user_tokens < order.quantity:
            raise HTTPException(status_code=400, detail="매도에 필요한 토큰량 부족")

        # 2. 주문 기록 저장 (Order_Archive 테이블)
        query = """
            INSERT INTO Order_Archive (property_id, user_id, order_type, price_per_token, quantity, remain, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (
            property_id, user_id, "sell", order.price_per_token, order.quantity, order.quantity, "normal"))
        conn.commit()

        order_id = cursor.lastrowid

        # 3. Redis 호가창 업데이트
        redis_key = f"order_book:{property_id}"
        existing_order_book = redis_client.hget(redis_key, "order_book")
        order_book = json.loads(existing_order_book) if existing_order_book else {"buy": {}, "sell": {}}
        if str(order.price_per_token) not in order_book["sell"]:
            order_book["sell"][str(order.price_per_token)] = []
        order_book["sell"][str(order.price_per_token)].append({"order_id": order_id, "quantity": order.quantity})

        update_order_book_in_redis(property_id, order_book)

    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    return {"message": "매도 주문이 완료", "order_id": order_id}


# REST API: 호가창 데이터 조회
@app.get("/api/orders/{property_id}")
async def get_order_book(property_id: int):
    redis_key = f"order_book:{property_id}"

    # Redis에서 전체 order_book 조회
    existing_order_book = redis_client.hget(redis_key, "order_book")  # HGET 사용

    if existing_order_book:
        try:
            order_book = json.loads(existing_order_book)  # JSON 디코딩
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Redis 데이터 디코딩 실패.")
    else:
        order_book = {"sell": {}, "buy": {}}
        redis_client.hset(redis_key, "order_book", json.dumps(order_book))  # Redis에 저장

    return {"property_id": property_id, "order_book": order_book}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)