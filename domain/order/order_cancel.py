from fastapi import APIRouter, HTTPException, Request
from core.settings import DB_CONFIG, REDIS_CLIENT
from core.jwt import extract_user_id
from core.redis import update_order_book_in_redis
import pymysql
import json

# 라우터 생성
router = APIRouter()

@router.delete("/{order_id}")
async def cancel_order(order_id: int, request: Request):
    # 쿠키에서 JWT 가져오기
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="쿠키에 JWT 없음")

    # JWT에서 유저 ID 가져오기
    try:
        user_id = extract_user_id(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"토큰 유효 X: {e}")

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. 주문 정보 가져오기
        query = """
            SELECT property_detail_id, status, order_type, price_per_token, quantity 
            FROM Order_Archive 
            WHERE id = %s AND user_id = %s
        """
        cursor.execute(query, (order_id, user_id))
        order = cursor.fetchone()

        if not order:
            raise HTTPException(status_code=404, detail="해당 주문을 찾을 수 없음")

        property_id, status, order_type, price_per_token, quantity = order

        if status != "normal":
            raise HTTPException(status_code=400, detail="해당 주문은 취소할 수 없는 상태")

        # 2. 주문 상태를 "cancelled"로 변경
        cursor.execute(
            "UPDATE Order_Archive SET status = 'cancelled' WHERE id = %s",
            (order_id,)
        )
        conn.commit()

        # 3. 주문 복원 로직
        if order_type == "buy":
            # 매수 주문 취소 -> 주문가능금액 복원
            total_cost = price_per_token * quantity
            cursor.execute(
                "UPDATE Users SET orderable_balance = orderable_balance + %s WHERE id = %s",
                (total_cost, user_id)
            )
        elif order_type == "sell":
            # 매도 주문 취소 -> 거래가능토큰수 복원
            cursor.execute(
                """
                UPDATE Ownerships 
                SET tradeable_tokens = tradeable_tokens + %s 
                WHERE user_id = %s AND property_detail_id = %s
                """,
                (quantity, user_id, property_id)
            )
        conn.commit()

        # 4. Redis 호가창에서 해당 주문 삭제
        redis_key = f"order_book:{property_id}"
        existing_order_book = REDIS_CLIENT.hget(redis_key, "order_book")
        if existing_order_book:
            order_book = json.loads(existing_order_book)
            order_list = order_book.get(order_type, {}).get(str(price_per_token), [])

            # 주문 ID로 해당 주문 제거
            order_list = [o for o in order_list if o["order_id"] != order_id]

            # 주문 목록이 비어 있으면 해당 가격 레벨 삭제
            if order_list:
                order_book[order_type][str(price_per_token)] = order_list
            else:
                del order_book[order_type][str(price_per_token)]

            # Redis에 업데이트
            update_order_book_in_redis(property_id, order_book)

    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    return {"message": "주문이 성공적으로 취소", "order_id": order_id}