from fastapi import APIRouter, HTTPException, Request
from core.settings import DB_CONFIG, REDIS_CLIENT
from core.jwt import extract_user_id
from core.redis import update_order_book_in_redis
import pymysql
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
async def submit_buy_order(
        order: BuyOrderRequest,
        property_id: int,
        request: Request
):
    # 쿠키에서 JWT 가져오기
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="쿠키에 JWT없음")

    # JWT에서 유저 ID 가져오기
    try:
        user_id = extract_user_id(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"토큰 유효 X {e}")

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. 사용자 주문 가능 금액(orderable_balance) 확인
        cursor.execute("SELECT orderable_balance FROM Users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="유저 정보를 찾을 수 없습니다.")

        orderable_balance = result[0]
        total_cost = order.quantity * order.price_per_token

        if orderable_balance < total_cost:
            raise HTTPException(status_code=400, detail="주문 가능한 잔액 부족")

        # 1-2. 주문 가능한 금액에서 제외 (update)
        cursor.execute(
            "UPDATE Users SET orderable_balance = orderable_balance - %s WHERE id = %s",
            (total_cost, user_id)
        )
        conn.commit()

        # 2. 주문 기록 저장 (Order_Archive 테이블)
        query = """
            INSERT INTO Order_Archive (property_detail_id, user_id, order_type, price_per_token, quantity, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (
            property_id, user_id, "buy", order.price_per_token, order.quantity, "normal"))
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
async def submit_sell_order(
        order: BuyOrderRequest,
        property_id: int,
        request: Request
):
    # 쿠키에서 JWT 가져오기
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="쿠키에 JWT없음")

    # JWT에서 유저 ID 가져오기
    try:
        user_id = extract_user_id(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"토큰 유효 X {e}")
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. 거래 가능 토큰 확인
        query = """
            SELECT tradeable_tokens 
            FROM Ownerships 
            WHERE user_id = %s AND property_id = %s
        """
        cursor.execute(query, (user_id, property_id))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="해당 토큰을 소유하고 있지 않음")

        tradeable_tokens = result[0]

        if tradeable_tokens < order.quantity:
            raise HTTPException(status_code=400, detail="매도에 필요한 거래 가능 토큰이 부족")

        #1-2. 거래 가능 토큰 업데이트 (차감)
        cursor.execute(
            "UPDATE Ownerships SET tradeable_tokens = tradeable_tokens - %s WHERE user_id = %s AND property_id = %s",
            (order.quantity, user_id, property_id)
        )
        conn.commit()

        # 2. 주문 기록 저장 (Order_Archive 테이블)
        query = """
            INSERT INTO Order_Archive (property_detail_id, user_id, order_type, price_per_token, quantity, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (
            property_id, user_id, "sell", order.price_per_token, order.quantity, "normal"))
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