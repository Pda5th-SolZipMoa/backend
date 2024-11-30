from datetime import datetime  # Modified part
from pymysql import connect
from core.mysql_connector import get_db_connection
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List
import shutil
import os,requests,json
from dotenv import load_dotenv
from pydantic import BaseModel

router = APIRouter()
IMAGE_DIR = "static/images/"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Load environment variables
load_dotenv()
SERVICE_KEY = os.getenv("PUBLIC_DATA_API_KEY")

# API basic URL
BUILDING_BASE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo"

# Data model for building information
class BuildingInfo(BaseModel):
    sigunguCd: str  # 시군구 코드
    bjdongCd: str   # 법정동 코드
    platGbCd: int   # 대지구분 코드
    bun: str        # 번
    ji: str         # 지

def fetch_building_info(building_info: BuildingInfo):
    """
    Fetch building information using the building ledger API.
    """
    params = {
        "serviceKey": SERVICE_KEY,
        "sigunguCd": building_info.sigunguCd,
        "bjdongCd": building_info.bjdongCd,
        "platGbCd": building_info.platGbCd,
        "bun": building_info.bun,
        "ji": building_info.ji,
        "_type": "json"
    }

    response = requests.get(BUILDING_BASE_URL, params=params)
    if response.status_code == 200:
        data = response.json()

        # Handle cases where data is missing
        if "response" in data and data["response"]["body"]["totalCount"] == "0":
            raise HTTPException(status_code=404, detail="건물 데이터를 찾을 수 없습니다.")

        items = data["response"]["body"]["items"]["item"]
        item = items[0] if isinstance(items, list) else items

        # Return cleaned data
        return {
            "대지면적": item.get("platArea"),  # Land area
            "건폐율": item.get("bcRat"),      # Building-to-land ratio
            "연면적": item.get("totArea"),     # Total floor area
            "용적률": item.get("vlRat")        # Floor area ratio
        }
    else:
        raise HTTPException(status_code=500, detail="건축물대장 API 호출 실패")

@router.post("/apartments/token")
async def create_property(
        name: str = Form(...),
        token_supply: int = Form(...),
        created_at: datetime = datetime.now(),
        price: int = Form(...),
        owner_id: int = 10,
        address: str = Form(...),
        building_code: str = Form(...),
        platArea: str = Form(None),
        bcRat: str = Form(None),
        totArea: str = Form(None),
        vlRat: str = Form(None),
        lat: float = Form(None),
        lng: float = Form(None),
        legalDocs: UploadFile = File(None),  # 위치 변경됨
        legalNotice: bool = Form(...),       # 위치 변경됨
        images: List[UploadFile] = File([]),
        detail_floor: int = Form(...),  # 필수로 변경
        home_size: str = Form(...),
        room_cnt: str = Form(...),
        maintenance_cost: str = Form(...),
):
    if not legalNotice:
        raise HTTPException(status_code=400, detail="이용 약관에 동의해야 합니다.")

    if not building_code:
        raise HTTPException(status_code=400, detail="building_code는 필수입니다.")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            # Properties 테이블에서 building_code 중복 확인
            select_query = "SELECT id FROM Properties WHERE building_code = %s"
            cursor.execute(select_query, (building_code,))
            result = cursor.fetchone()

            if result:
                # 이미 존재하는 building_code일 경우
                property_id = result['id']
                print(f"기존 property_id: {property_id}")
            else:
                # 존재하지 않는 building_code일 경우 Properties에 데이터 삽입
                insert_property_query = """
                    INSERT INTO Properties (name, token_supply, created_at, price, owner_id, address, building_code, platArea, bcRat, totArea, vlRat, lat, lng)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_property_query, (
                    name, token_supply, created_at, price, owner_id, address,
                    building_code, platArea, bcRat, totArea, vlRat, lat, lng
                ))
                property_id = cursor.lastrowid
                print(f"새로운 property_id: {property_id}")

            # 이미지 처리: 여러 이미지 저장
            image_urls = []
            for image in images:
                if image:
                    file_name = f"property_{property_id}_{os.path.basename(image.filename)}"
                    file_path = os.path.join(IMAGE_DIR, file_name)

                    with open(file_path, "wb+") as file_object:
                        shutil.copyfileobj(image.file, file_object)

                    image_urls.append(file_path)  # 이미지 경로를 리스트에 추가

            # 이미지 URL 리스트를 JSON 문자열로 변환
            home_photos_json = json.dumps(image_urls, ensure_ascii=False)

            # legalDocs 처리
            legalDocs_path = None
            if legalDocs:
                legalDocs_filename = f"legalDocs_{property_id}_{os.path.basename(legalDocs.filename)}"
                legalDocs_path = os.path.join(IMAGE_DIR, legalDocs_filename)
                with open(legalDocs_path, "wb+") as file_object:
                    shutil.copyfileobj(legalDocs.file, file_object)

            # Property_Detail 테이블에 데이터 삽입
            insert_detail_query = """
                INSERT INTO Property_Detail (property_id, detail_floor, home_size, room_cnt, maintenance_cost, home_photos, legalDocs, legalNotice)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_detail_query, (
                property_id, detail_floor, home_size, room_cnt, maintenance_cost, home_photos_json, legalDocs_path, int(legalNotice)
            ))

            conn.commit()
            return {"message": "데이터가 성공적으로 저장되었습니다.", "property_id": property_id}

        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

        finally:
            cursor.close()
#수정본
# @router.post("/apartments/token")
# async def create_property(
#         name: str = Form(...),
#         token_supply: int = Form(...),
#         created_at: datetime = datetime.now(),
#         price: int = Form(...),
#         owner_id: int = 10,
#         address: str = Form(...),
#         building_code: str = Form(None),
#         platArea: str = Form(None),
#         bcRat: str = Form(None),
#         totArea: str = Form(None),
#         vlRat: str = Form(None),
#         lat: float = Form(None),
#         lng: float = Form(None),
#         legalDocs: UploadFile = File(None),
#         legalNotice: bool = Form(...),
#         images: List[UploadFile] = File([]),
#         detail_floor: int = Form(None),  # 추가된 필드
#         home_size: str = Form(None),
#         room_cnt: str = Form(None),
#         maintenance_cost: str = Form(None),
# ):
#     # `building_code`가 있는 경우
#     if not building_code:
#         raise HTTPException(status_code=400, detail="building_code는 필수입니다.")
#
#     with get_db_connection() as conn:
#         cursor = conn.cursor()
#
#         try:
#             # `Properties` 테이블에서 building_code 중복 여부 확인
#             select_query = "SELECT id FROM Properties WHERE building_code = %s"
#             cursor.execute(select_query, (building_code,))
#             result = cursor.fetchone()
#             print(result['id'])
#             if result:
#                 # 이미 존재하는 building_code일 경우
#                 property_id = result['id']
#                 print(f"기존 property_id: {property_id}")
#             else:
#                 # 존재하지 않는 building_code일 경우 `Properties`에 데이터 삽입
#                 insert_property_query = """
#                     INSERT INTO Properties (name, token_supply, created_at, price, owner_id, address, building_code, platArea, bcRat, totArea, vlRat, lat, lng, legalDocs, legalNotice)
#                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#                 """
#                 cursor.execute(insert_property_query, (
#                     name, token_supply, created_at, price, owner_id, address,
#                     building_code, platArea, bcRat, totArea, vlRat, lat, lng, None, int(legalNotice)
#                 ))
#                 property_id = cursor.lastrowid
#                 print(f"새로운 property_id: {property_id}")
#
#                 # 이미지 삽입 처리
#                 for image in images:
#                     if image:
#                         file_name = f"property_{property_id}_{os.path.basename(image.filename)}"
#                         file_path = os.path.join(IMAGE_DIR, file_name)
#
#                         with open(file_path, "wb+") as file_object:
#                             shutil.copyfileobj(image.file, file_object)
#
#                         insert_photo_query = """
#                             INSERT INTO Property_Photos (property_id, url)
#                             VALUES (%s, %s)
#                         """
#                         cursor.execute(insert_photo_query, (property_id, file_path))
#
#             # `property_detail_info` 테이블에 데이터 삽입
#             insert_detail_query = """
#                 INSERT INTO Property_Detail (property_id, detail_floor, home_size, room_cnt, maintenance_cost)
#                 VALUES (%s, %s, %s, %s, %s)
#             """
#             cursor.execute(insert_detail_query, (
#                 property_id, detail_floor, home_size, room_cnt, maintenance_cost
#             ))
#
#             conn.commit()
#             return {"message": "데이터가 성공적으로 저장되었습니다.", "property_id": property_id}
#
#         except Exception as e:
#             conn.rollback()
#             raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
#
#         finally:
#             cursor.close()


