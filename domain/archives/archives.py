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
                SELECT 
                    oa.id,
                    oa.order_type, 
                    oa.price_per_token, 
                    oa.quantity, 
                    oa.status, 
                    oa.created_at,
                    pd.detail_floor,
                    b.name AS building_name
                FROM Order_Archive oa
                LEFT JOIN Property_Detail pd ON oa.property_detail_id = pd.id
                LEFT JOIN Properties b ON pd.property_id = b.id
                WHERE oa.user_id = %s AND oa.status = %s
                ORDER BY oa.created_at DESC
                """,
                (user_id, status)
            )
        else:
            cursor.execute(
                """
                SELECT 
                    oa.id,
                    oa.order_type, 
                    oa.price_per_token, 
                    oa.quantity, 
                    oa.status, 
                    oa.created_at,
                    pd.detail_floor,
                    b.name AS building_name
                FROM Order_Archive oa
                LEFT JOIN Property_Detail pd ON oa.property_detail_id = pd.id
                LEFT JOIN Properties b ON pd.property_id = b.id
                WHERE oa.user_id = %s
                ORDER BY oa.created_at DESC
                """,
                (user_id,)
            )

        results = cursor.fetchall()

        if not results:
            raise HTTPException(status_code=404, detail="주문 기록을 찾을 수 없습니다.")

        orders = [
            {
                "id": row[0],
                "order_type": row[1],
                "price_per_token": row[2],
                "quantity": row[3],
                "status": row[4],
                "created_at": row[5],
                "detail_floor": row[6],
                "building_name": row[7],
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