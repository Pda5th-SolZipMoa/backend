from fastapi import APIRouter, HTTPException, Request, Query
from core.settings import DB_CONFIG
from core.jwt import extract_user_id
import pymysql

# 라우터 생성
router = APIRouter()

# 사용자 주문 기록 조회 API
@router.get("/")
async def get_user_order_archives(
        request: Request,
        status: str = Query(None, description="조회할 주문 상태 (예: 'normal', 'cancelled', 'fulfilled')")
):
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

        # 주문 상태별로 필터링하여 주문 기록 조회
        if status:
            cursor.execute(
                """
                SELECT order_type, price_per_token, quantity, status, created_at 
                FROM Order_Archive 
                WHERE user_id = %s AND status = %s
                ORDER BY created_at DESC
                """,
                (user_id, status)
            )
        else:
            cursor.execute(
                """
                SELECT order_type, price_per_token, quantity, status, created_at 
                FROM Order_Archive 
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )

        results = cursor.fetchall()

        if not results:
            raise HTTPException(status_code=404, detail="주문 기록을 찾을 수 없습니다.")

        orders = [
            {
                "order_type": row[0],
                "price_per_token": row[1],
                "quantity": row[2],
                "status": row[3],
                "created_at": row[4],
            }
            for row in results
        ]
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    return {
        "user_id": user_id,
        "orders": orders,
    }