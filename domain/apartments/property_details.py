from fastapi import APIRouter, HTTPException
import pymysql
from core.settings import DB_CONFIG

# 라우터 생성
router = APIRouter()

@router.get("/{property_id}")
async def get_property_details(property_id: int):
    """
    주어진 건물 ID에 해당하는 방 ID, 층수, 관리비, 평수를 반환하는 API
    """
    try:
        # DB 연결
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # SQL 쿼리 실행
        cursor.execute(
            """
            SELECT 
                id AS room_id,
                detail_floor,
                maintenance_cost,
                home_size
            FROM Property_Detail
            WHERE property_id = %s
            """,
            (property_id,)
        )
        results = cursor.fetchall()

        # 결과가 없을 경우 예외 처리
        if not results:
            raise HTTPException(status_code=404, detail="해당 건물 ID에 대한 정보를 찾을 수 없습니다.")

        # 데이터를 가공하여 반환
        rooms = [
            {
                "room_id": row[0],
                "detail_floor": row[1],
                "maintenance_cost": row[2],
                "home_size": row[3],
            }
            for row in results
        ]
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        # 리소스 정리
        cursor.close()
        conn.close()

    return {
        "property_id": property_id,
        "rooms": rooms,
    }