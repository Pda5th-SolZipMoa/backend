from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
import pymysql
import redis
import jwt
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import json

# .env 파일 로드
load_dotenv()

# MySQL 설정
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database":os.getenv("DB_NAME"),
    "charset": os.getenv("DB_CHARSET"),
}

# Redis 설정
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    db=int(os.getenv("REDIS_DB")),
    decode_responses=True
)

# JWT Secret Key
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# FastAPI 앱 생성
app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic 모델
class BuyOrderRequest(BaseModel):
    quantity: int
    price_per_token: int

# JWT 인증 함수
def verify_jwt(token: str):
    try:
        decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        return decoded["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

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

        # 방금 삽입된 주문 ID 가져오기
        order_id = cursor.lastrowid

        # 3. Redis 호가창 업데이트
        redis_key = f"order_book:{property_id}"
        existing_order_book = redis_client.hget(redis_key, "order_book")

        # Redis 데이터 처리
        if existing_order_book:
            try:
                order_book = json.loads(existing_order_book)  # JSON으로 변환
                if not isinstance(order_book, dict) or "buy" not in order_book or "sell" not in order_book:
                    raise ValueError("Redis 데이터 구조가 올바르지 않습니다.")  # 강제 오류 발생
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Redis 데이터 디코딩 실패.")
        else:
            # 새로운 호가창 생성
            order_book = {"buy": {}, "sell": {}}

        # 데이터 추가
        buy_orders = order_book["buy"]
        if str(order.price_per_token) not in buy_orders:
            buy_orders[str(order.price_per_token)] = []

        buy_orders[str(order.price_per_token)].append({
            "order_id": order_id,
            "quantity": order.quantity
        })

        # Redis에 다시 저장
        redis_client.hset(redis_key, "order_book", json.dumps(order_book))

    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    except ValueError as ve:
        raise HTTPException(status_code=500, detail=str(ve))
    finally:
        cursor.close()
        conn.close()

    return {"message": "매수 주문이 완료", "order_id": order_id}

class SellOrderRequest(BaseModel):
    quantity: int
    price_per_token: int

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

        # 방금 삽입된 주문 ID 가져오기
        order_id = cursor.lastrowid

        # 3. Redis 호가창 업데이트
        redis_key = f"order_book:{property_id}"
        existing_order_book = redis_client.hget(redis_key, "order_book")  # HGET 사용

        if existing_order_book:
            try:
                order_book = json.loads(existing_order_book)  # JSON 디코딩
                if not isinstance(order_book, dict) or "buy" not in order_book or "sell" not in order_book:
                    raise ValueError("Redis 데이터 구조가 올바르지 않습니다.")
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Redis 데이터 디코딩 실패.")
        else:
            order_book = {"buy": {}, "sell": {}}  # 빈 order_book 초기화

        # 데이터 추가
        sell_orders = order_book["sell"]
        if str(order.price_per_token) not in sell_orders:
            sell_orders[str(order.price_per_token)] = []

        sell_orders[str(order.price_per_token)].append({
            "order_id": order_id,
            "quantity": order.quantity
        })

        # Redis에 다시 저장
        redis_client.hset(redis_key, "order_book", json.dumps(order_book))  # HSET 사용

    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    return {"message": "매도 주문이 완료", "order_id": order_id}

@app.get("/api/orders/{property_id}")
async def get_order_book(property_id: int):
    """
    특정 property_id의 호가창 데이터를 조회합니다.
    데이터가 없으면 Redis에 빈 호가창 생성 후 반환.
    """
    redis_key = f"order_book:{property_id}"

    # Redis에서 전체 order_book 조회
    existing_order_book = redis_client.hget(redis_key, "order_book")  # HGET 사용

    if existing_order_book:
        try:
            order_book = json.loads(existing_order_book)  # JSON 디코딩
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Redis 데이터 디코딩 실패.")
    else:
        # 데이터가 없으면 빈 order_book 생성
        order_book = {"sell": {}, "buy": {}}
        redis_client.hset(redis_key, "order_book", json.dumps(order_book))  # Redis에 저장

        return {
            "property_id": property_id,
            "order_book": order_book,
            "message": "Empty order book created."
        }

    return {
        "property_id": property_id,
        "order_book": order_book
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)