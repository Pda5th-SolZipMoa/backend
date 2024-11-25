from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from datetime import datetime, timedelta

from core.mysql_connector import get_db_connection

# 환경 변수 로드
load_dotenv()
SERVICE_KEY = os.getenv("PUBLIC_DATA_API_KEY")

# APIRouter 사용
router = APIRouter()

# API 기본 URL
BUILDING_BASE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo"
APARTMENT_BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# 요청 본문 데이터 모델
class BuildingInfo(BaseModel):
    sigunguCd: str  # 시군구 코드
    bjdongCd: str   # 법정동 코드
    platGbCd: int   # 대지구분 코드
    bun: str        # 번
    ji: str         # 지

def normalize_number(number_str):
    """
    숫자 문자열의 앞쪽에 있는 0을 제거하고, 잘못된 입력에 대해 None을 반환합니다.
    """
    if number_str is None:
        return None
    number_str = number_str.strip()
    if not number_str or not number_str.isdigit():
        return None
    return str(int(number_str))  # 앞쪽의 0 제거

def is_bubun_match(requested_bubun, api_bubun):
    """
    부번 값을 비교하며, 부번이 없거나 0인 경우를 고려합니다.
    """
    if requested_bubun is None:
        return api_bubun in [None, '', '0']
    else:
        return requested_bubun == api_bubun

def fetch_building_info(building_info: BuildingInfo):
    """
    건축물대장 API를 사용하여 건물 정보를 가져옵니다.
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

        # 데이터가 없는 경우 처리
        if "response" in data and data["response"]["body"]["totalCount"] == "0":
            raise HTTPException(status_code=404, detail="건물 데이터를 찾을 수 없습니다.")

        items = data["response"]["body"]["items"]["item"]
        item = items[0] if isinstance(items, list) else items

        # 정리된 데이터 반환
        return {
            "대지면적": item.get("platArea"),  # 대지면적
            "건폐율": item.get("bcRat"),      # 건폐율
            "연면적": item.get("totArea"),     # 연면적
            "용적률": item.get("vlRat")        #용적률
        }
    else:
        raise HTTPException(status_code=500, detail="건축물대장 API 호출 실패")

def fetch_apartment_transactions(service_key, lawd_cd, bonbun, bubun=None, max_results=5):
    """
    특정 번지 및 부번에 대한 최신 아파트 거래 내역을 가져옵니다.
    """
    transactions = []
    today = datetime.now()

    # 요청된 본번과 부번을 정규화
    requested_bonbun = normalize_number(bonbun)
    requested_bubun = normalize_number(bubun)

    # 최근 12개월 동안의 거래를 탐색
    for i in range(12):
        target_date = today - timedelta(days=i * 30)
        deal_ymd = target_date.strftime("%Y%m")  # YYYYMM 형식

        page_no = 1
        while True:
            params = {
                'serviceKey': service_key,
                'LAWD_CD': lawd_cd,
                'DEAL_YMD': deal_ymd,
                'numOfRows': 100,
                'pageNo': page_no,
            }

            response = requests.get(APARTMENT_BASE_URL, params=params)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                body = root.find('body')

                # 데이터가 없으면 반복 종료
                if body is None or body.find('items') is None:
                    break

                items = body.find('items').findall('item')
                for item in items:
                    # API 응답에서 본번과 부번을 가져와 정규화
                    api_bonbun = normalize_number(item.findtext('bonbun', default=''))
                    api_bubun = normalize_number(item.findtext('bubun', default=''))

                    if api_bonbun == requested_bonbun and is_bubun_match(requested_bubun, api_bubun):
                        transactions.append({
                            '아파트명': item.findtext('aptNm', default='').strip(),
                            '거래금액': item.findtext('dealAmount', default='').strip(),
                            '전용면적': item.findtext('excluUseArea', default='').strip(),
                            '층': item.findtext('floor', default='').strip(),
                            '계약연도':item.findtext('dealYear',default='').strip(),
                            '계약월': item.findtext('dealMonth', default='').strip(),
                            '계약일': item.findtext('dealDay', default='').strip(),
                        })

                        # 최대 결과 수에 도달하면 반환
                        if len(transactions) >= max_results:
                            return transactions

                # 다음 페이지로 이동
                page_no += 1

                # 모든 페이지를 탐색했는지 확인
                total_count = int(body.findtext('totalCount', default='0'))
                if page_no > (total_count // 100 + 1):
                    break
            else:
                break

    # 발견된 거래 내역 반환
    return transactions

@router.post("/building-latest-transactions")
async def get_building_and_transactions(building_info: BuildingInfo):
    """
    건물 정보와 최신 아파트 거래 5건을 반환하는 API 엔드포인트
    """
    try:
        # 건물 정보 가져오기
        building_summary = fetch_building_info(building_info)

        # 아파트 거래 정보를 위한 파라미터 준비
        lawd_cd = building_info.sigunguCd  # 지역 코드 (5자리 LAWD_CD)
        bonbun = building_info.bun
        bubun = building_info.ji if building_info.ji != '0' else None

        # 아파트 거래 정보 가져오기
        latest_transactions = fetch_apartment_transactions(SERVICE_KEY, lawd_cd, bonbun, bubun)

        # 거래 내역이 없는 경우 처리
        if not latest_transactions:
            latest_transactions = {"message": "최근 거래 내역이 없습니다."}

        return JSONResponse(content={
            "건물정보": building_summary,
            "최신거래": latest_transactions
        })

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
