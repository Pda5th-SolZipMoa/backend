from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from fastapi.concurrency import run_in_threadpool
from core.mysql_connector import get_db_connection

# 라우터 생성
router = APIRouter()

# 응답 모델 정의
class PhotoResponse(BaseModel):
    url: str
    order: int

class BuildingResponse(BaseModel):
    id: int
    name: str
    token_supply: int
    created_at: datetime
    price: float
    address: str
    building_code: str
    owner_id: int
    photos: List[PhotoResponse]
    lat: float
    lng: float

# 엔드포인트 정의
@router.get("/buildings", response_model=List[BuildingResponse])
async def get_buildings_with_photos():
    """
    건물 데이터와 해당 건물의 사진 데이터를 반환하는 엔드포인트
    """
    def fetch_buildings_with_photos():
        query = """
            SELECT 
                p.id AS building_id,
                p.name,
                p.token_supply,
                p.created_at,
                p.price,
                p.address,
                p.building_code,
                p.owner_id,
                p.lat,
                p.lng,
                pp.url AS photo_url,
                pp.display_order AS photo_order
            FROM 
                Properties p
            LEFT JOIN 
                Property_Photos pp
            ON 
                p.id = pp.property_id
            ORDER BY 
                p.id, pp.display_order;
        """
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()

    try:
        results = await run_in_threadpool(fetch_buildings_with_photos)

        # 데이터 가공: 건물별 사진 리스트 그룹화
        buildings = {}
        for row in results:
            building_id = row["building_id"]
            if building_id not in buildings:
                buildings[building_id] = {
                    "id": building_id,
                    "name": row["name"],
                    "token_supply": row["token_supply"],
                    "created_at": row["created_at"],
                    "price": row["price"],
                    "address": row["address"],
                    "building_code": row["building_code"],
                    "owner_id": row["owner_id"],
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "photos": [],
                }
            if row["photo_url"]:
                buildings[building_id]["photos"].append({
                    "url": row["photo_url"],
                    "order": row["photo_order"],
                })

        return list(buildings.values())

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")
