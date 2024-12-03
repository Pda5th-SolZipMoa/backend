from fastapi import APIRouter, HTTPException
from core.settings import DB_CONFIG
import pymysql

# 라우터 생성
router = APIRouter()

# 건물 단일가매매 기록 조회 API


@router.get("/{property_id}/history")
async def get_property_history(property_id: int):
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 최신 날짜 기준으로 100개 조회
        query = """
            SELECT recorded_date, price, quantity
            FROM Property_History
            WHERE property_detail_id = %s
            ORDER BY recorded_date DESC
            LIMIT 100
        """

        cursor.execute(query, (property_id,))
        results = cursor.fetchall()

        if not results:
            raise HTTPException(status_code=404, detail="해당 건물의 매매 기록이 없습니다.")

        # 결과 데이터 처리
        history = [
            {"recorded_date": str(row[0]), "price": row[1], "quantity": row[2]}
            for row in results
        ]
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    return {
        "property_id": property_id,
        "history": history
    }
