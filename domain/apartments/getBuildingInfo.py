from fastapi import APIRouter, HTTPException, Query
from core.mysql_connector import get_db_connection

router = APIRouter()


@router.get("/properties/check")
async def check_building_info(building_code: str = Query(..., description="빌딩 코드")):
    """
    빌딩 코드가 Properties 테이블에 존재하는지 확인합니다.
    """
    if not building_code:
        raise HTTPException(status_code=400, detail="building_code는 필수입니다.")

    query = "SELECT COUNT(*) AS count FROM Properties WHERE building_code = %s"

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (building_code,))
                result = cursor.fetchone()
                exists = result["count"] > 0

        return {"exists": exists}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 조회 중 오류가 발생했습니다: {e}")
