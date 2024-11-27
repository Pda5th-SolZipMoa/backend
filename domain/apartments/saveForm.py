from datetime import datetime  # Modified part
from pymysql import connect
from core.mysql_connector import get_db_connection
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List
import shutil
import os
import requests
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
        created_at: datetime = datetime.now(),  # Modified part
        price: int = Form(...),
        owner_id: int = 10,
        address: str = Form(...),
        building_code: str = Form(None),
        platArea: str = Form(None),
        bcRat: str = Form(None),
        totArea: str = Form(None),
        vlRat: str = Form(None),
        lat: float = Form(None),
        lng: float = Form(None),
        legalDocs: UploadFile = File(None),
        legalNotice: bool = Form(...),
        images: List[UploadFile] = File([]),
):
    # Log received data
    print("Name:", name)
    print("Token Supply:", token_supply)
    print("Created At:", created_at)
    print("Price:", price)
    print("Owner ID:", owner_id)
    print("Address:", address)
    print('BuildingCode:', building_code)
    print("Latitude:", lat)
    print("Longitude:", lng)
    print("Legal Docs:", legalDocs.filename if legalDocs else "None")
    print("Legal Notice:", legalNotice)
    print("Images:", [image.filename for image in images])

    if not legalNotice:
        raise HTTPException(status_code=400, detail="이용 약관에 동의해야 합니다.")

    if building_code:
        try:
            # Parse the building_code
            sigunguCd = building_code[0:5]
            bjdongCd = building_code[5:10]
            platGbCd = building_code[10]
            bun = building_code[11:15]
            ji = building_code[15:19]

            # Create BuildingInfo object
            building_info = BuildingInfo(
                sigunguCd=sigunguCd,
                bjdongCd=bjdongCd,
                platGbCd=int(platGbCd),
                bun=bun,
                ji=ji
            )

            # Fetch building info
            building_summary = fetch_building_info(building_info)

            # Map the values
            platArea = building_summary.get('대지면적')
            bcRat = building_summary.get('건폐율')
            totArea = building_summary.get('연면적')
            vlRat = building_summary.get('용적률')

            # Log fetched data
            print("Fetched platArea:", platArea)
            print("Fetched bcRat:", bcRat)
            print("Fetched totArea:", totArea)
            print("Fetched vlRat:", vlRat)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch building info: {str(e)}")

    # Ensure that the required fields are not None
    if not all([platArea, bcRat, totArea, vlRat]):
        raise HTTPException(status_code=400, detail="건물 정보를 가져올 수 없습니다.")

    # Process legalDocs if provided
    if legalDocs:
        legalDocs_filename = f"legalDocs_{name}_{legalDocs.filename}"
        legalDocs_path = os.path.join(IMAGE_DIR, legalDocs_filename)
        with open(legalDocs_path, "wb+") as file_object:
            shutil.copyfileobj(legalDocs.file, file_object)
    else:
        legalDocs_path = None

    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            # Insert data into Properties table
            insert_property_query = """
                INSERT INTO Properties (name, token_supply, created_at, price, owner_id, address, building_code, platArea, bcRat, totArea, vlRat, lat, lng, legalDocs, legalNotice)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_property_query, (
                name, token_supply, created_at, price, owner_id, address,
                building_code, platArea, bcRat, totArea, vlRat, lat, lng, legalDocs_path, int(legalNotice)
            ))

            property_id = cursor.lastrowid

            # Process images and insert data into Property_Photos table
            for image in images:
                if image:
                    file_extension = os.path.splitext(image.filename)[1]
                    file_name = f"property_{property_id}_{os.path.basename(image.filename)}"  # Modified part
                    file_path = os.path.join(IMAGE_DIR, file_name)

                    with open(file_path, "wb+") as file_object:
                        shutil.copyfileobj(image.file, file_object)

                    insert_photo_query = """
                        INSERT INTO Property_Photos (property_id, url)
                        VALUES (%s, %s)
                    """
                    cursor.execute(insert_photo_query, (property_id, file_path))

            conn.commit()
            return {"message": "Property token created successfully", "property_id": property_id}

        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

        finally:
            cursor.close()
