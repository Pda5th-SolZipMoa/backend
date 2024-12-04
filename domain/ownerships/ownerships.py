from fastapi import APIRouter, HTTPException, Request
from core.settings import DB_CONFIG
from core.jwt import extract_user_id
import pymysql

# 라우터 생성
router = APIRouter()

# 사용자 보유 토큰 반환 API
@router.get("/")
async def get_user_ownerships(request: Request):
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

        # 한 번의 쿼리로 데이터 가져오기
        cursor.execute(
            """
            SELECT 
                o.property_detail_id,
                o.quantity,
                o.buy_price,
                pd.detail_floor,
                b.name AS building_name,
                (
                    SELECT price
                    FROM Property_History ph
                    WHERE ph.property_detail_id = o.property_detail_id
                    ORDER BY ph.recorded_date DESC
                    LIMIT 1
                ) AS latest_price
            FROM Ownerships o
            JOIN Property_Detail pd ON o.property_detail_id = pd.id
            JOIN Properties b ON pd.property_id = b.id
            WHERE o.user_id = %s
            """,
            (user_id,)
        )
        results = cursor.fetchall()

        if not results:
            raise HTTPException(status_code=404, detail="보유 토큰 정보를 찾을 수 없습니다.")

        # 데이터를 리스트로 변환
        ownerships = [
            {
                "property_detail_id": row[0],
                "quantity": row[1],
                "buy_price": row[2],
                "detail_floor": row[3],
                "building_name": row[4],
                "latest_price": row[5] if row[5] else 0,
                "eval_value": (row[5] * row[1]) if row[5] else 0
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
        "ownerships": ownerships,
    }