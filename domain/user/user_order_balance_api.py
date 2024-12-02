from fastapi import APIRouter, HTTPException, Request
from core.settings import DB_CONFIG
from core.jwt import extract_user_id
import pymysql

# 라우터 생성
router = APIRouter()

# 주문가능금액 반환 API
@router.get("/buy-order-balance")
async def get_user_orderable_balance(request: Request):
    # JWT에서 유저 ID 추출
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="쿠키에 JWT 없음")

    try:
        user_id = extract_user_id(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"유효하지 않은 토큰: {e}")

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Users 테이블에서 유저의 보유금액(total_balance)와 주문가능금액(orderable_balance) 조회
        cursor.execute(
            "SELECT total_balance, orderable_balance FROM Users WHERE id = %s",
            (user_id,)
        )
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="유저 정보를 찾을 수 없습니다.")

        total_balance, orderable_balance = result
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    return {
        "user_id": user_id,
        "total_balance": total_balance,
        "orderable_balance": orderable_balance,
    }

# 거래가능토큰 반환 API
@router.get("/sell-order-balance/{property_id}")
async def get_user_tradeable_tokens(property_id: int, request: Request):
    # JWT에서 유저 ID 추출
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="쿠키에 JWT 없음")

    try:
        user_id = extract_user_id(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"유효하지 않은 토큰: {e}")

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Ownerships 테이블에서 유저의 특정 방에 대한 거래가능토큰(tradeable_tokens) 조회
        cursor.execute(
            """
            SELECT quantity, tradeable_tokens 
            FROM Ownerships 
            WHERE user_id = %s AND property_detail_id = %s
            """,
            (user_id, property_id)
        )
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="거래가능토큰 정보를 찾을 수 없습니다.")

        quantity, tradeable_tokens = result
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    return {
        "user_id": user_id,
        "property_id": property_id,
        "tradeable_tokens": tradeable_tokens,
        "quantity": quantity,
    }