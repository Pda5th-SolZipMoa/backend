import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from fastapi.concurrency import run_in_threadpool
from core.mysql_connector import get_db_connection

# 라우터 생성
router = APIRouter()

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# 응답 모델 정의
class PhotoResponse(BaseModel):
    url: str
    order: int

class BuildingResponse(BaseModel):
    id: int
    name: str
    token_supply: int
    token_cost: float  # token_cost 추가
    created_at: datetime
    price: float
    address: str
    building_code: str
    owner_id: int
    photos: List[PhotoResponse]
    lat: float
    lng: float
    status: Optional[str] 

# 엔드포인트 정의
@router.get("/buildings", response_model=List[BuildingResponse])
async def get_buildings_with_photos():
    """
    건물 데이터와 해당 건물의 사진, token_supply 및 token_cost 데이터를 반환하는 엔드포인트
    """
    def fetch_buildings_with_photos():
        query = """
            SELECT 
                p.id AS building_id,
                p.name,
                pd.token_supply,  -- Property_Detail 테이블에서 token_supply를 가져옵니다
                pd.token_cost,    -- Property_Detail 테이블에서 token_cost를 가져옵니다
                p.created_at,
                p.price,
                p.address,
                p.building_code,
                p.owner_id,
                p.lat,
                p.lng,
                p.status,
                p.property_photo AS photo_url  -- 대표 사진을 가져옴
            FROM 
                Properties p
            LEFT JOIN 
                Property_Detail pd ON p.id = pd.property_id  -- Property_Detail 테이블과 조인
            ORDER BY 
                p.id;
        """
        try:
            with get_db_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    return cursor.fetchall()
        except Exception as e:
            logging.error(f"Database query failed: {e}")
            raise HTTPException(status_code=500, detail="Database query failed")

    try:
        # 데이터베이스 쿼리 비동기 처리
        results = await run_in_threadpool(fetch_buildings_with_photos)

        # 데이터 가공: 건물별 사진 리스트 그룹화
        buildings = {}
        for row in results:
            building_id = row["building_id"]
            if building_id not in buildings:
                buildings[building_id] = {
                    "id": building_id,
                    "name": row["name"],
                    "token_supply": row["token_supply"],  # token_supply 값을 설정
                    "token_cost": row["token_cost"],  # token_cost 값을 설정
                    "created_at": row["created_at"],
                    "price": row["price"],
                    "address": row["address"],
                    "building_code": row["building_code"],
                    "owner_id": row["owner_id"],
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "photos": [],
                    "status": row["status"],  # 올바르게 row["status"]로 변경

                }

            # 대표 사진 추가
            if row.get("photo_url"):
                buildings[building_id]["photos"].append({
                    "url": row["photo_url"],
                    "order": 1,  # 대표 사진의 경우 기본 order 1로 설정
                })

        return list(buildings.values())

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
