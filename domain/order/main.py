from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from contextlib import asynccontextmanager
from core.settings import DB_CONFIG, REDIS_CLIENT
from core.websockets import manager
import pymysql
import asyncio
import json
from pydantic import BaseModel

# 라우터 생성
router = APIRouter()

# Pydantic 모델 정의
class BuyOrderRequest(BaseModel):
    quantity: int
    price_per_token: int

class SellOrderRequest(BaseModel):
    quantity: int
    price_per_token: int

# 주문 제출 API (매수)
@router.post("/{property_id}/buy")
async def submit_buy_order(order: BuyOrderRequest, property_id: int):
    # TODO: JWT에서 유저 ID 가져오기
    user_id = 1
    try:
        conn = pymysql.connect(**DB_CONFIG)
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
        existing_order_book = REDIS_CLIENT.hget(redis_key, "order_book")
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
@router.post("/{property_id}/sell")
async def submit_sell_order(order: SellOrderRequest, property_id: int):
    # TODO: JWT에서 유저 ID 가져오기
    user_id = 1
    try:
        conn = pymysql.connect(**DB_CONFIG)
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
        existing_order_book = REDIS_CLIENT.hget(redis_key, "order_book")
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

# REST API: 호가창 조회
@router.get("/{property_id}")
async def get_order_book(property_id: int):
    redis_key = f"order_book:{property_id}"
    # Redis에서 전체 order_book 조회
    existing_order_book = REDIS_CLIENT.hget(redis_key, "order_book")
    if existing_order_book:
        try:
            order_book = json.loads(existing_order_book)  # JSON 디코딩
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Redis 데이터 디코딩 실패.")
    else:
        order_book = {"sell": {}, "buy": {}}
        REDIS_CLIENT.hset(redis_key, "order_book", json.dumps(order_book))  # Redis에 저장
    return {"property_id": property_id, "order_book": order_book}


# Redis Pub/Sub Listener
async def redis_listener():
    # Redis 채널 구독
    pubsub = REDIS_CLIENT.pubsub()
    pubsub.subscribe("order_book_updates")
    print("Redis listener started, subscribed to 'order_book_updates'")
    try:
        while True:
            # Redis에서 메시지 수신
            message = pubsub.get_message()
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                property_id = data.get("property_id")
                if property_id:
                    # WebSocket으로 브로드캐스트
                    await manager.broadcast(json.dumps(data), property_id)
            await asyncio.sleep(0.01)  # Redis 메시지 폴링 간격
    except Exception as e:
        print(f"Redis listener error: {e}")

# Redis 데이터 업데이트 및 Pub/Sub 메시지 발행
def update_order_book_in_redis(property_id: int, order_book: dict):
    redis_key = f"order_book:{property_id}"
    REDIS_CLIENT.hset(redis_key, "order_book", json.dumps(order_book))
    update_message = {"property_id": property_id, "order_book": order_book}
    REDIS_CLIENT.publish("order_book_updates", json.dumps(update_message))





# # FastAPI 앱 생성
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     print("Application startup")
#     loop = asyncio.get_event_loop()
#     loop.create_task(redis_listener())
#     yield
#     print("Application shutdown")
#
# app = FastAPI(lifespan=lifespan)
# app.include_router(router, prefix="/api", tags=["orders"])
#
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)