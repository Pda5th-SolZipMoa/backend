from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from core.mysql_connector import get_db_connection
from datetime import datetime


# APIRouter 사용
router = APIRouter()

def fetch_building_info(building_id: int):
    """
    데이터베이스를 사용하여 건물 정보를 가져옵니다.
    """
    try:
        # 데이터베이스 연결
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                # 건물 기본 정보 가져오기
                query = """
                    SELECT building_code, platArea, bcRat, totArea, vlRat, name, address
                    FROM Properties
                    WHERE id = %s
                """
                params = (building_id,)
                cursor.execute(query, params)
                result = cursor.fetchone()

                if not result:
                    raise HTTPException(status_code=404, detail="건물 데이터를 찾을 수 없습니다.")

                building_summary = {
                    "대지면적": result.get("platArea"),
                    "건폐율": result.get("bcRat"),
                    "연면적": result.get("totArea"),
                    "용적률": result.get("vlRat"),
                    "건물명": result.get("name"),
                    "주소": result.get("address"),
                }

                # 이미지 URL 가져오기
                photo_query = """
                    SELECT url
                    FROM Property_Photos
                    WHERE property_id = %s
                """
                cursor.execute(photo_query, params)
                photos = cursor.fetchall()

                # 이미지 URL 리스트 생성
                image_urls = [photo['url'] for photo in photos] if photos else []

                # 건물 요약 정보에 이미지 URL 추가
                building_summary['이미지URL'] = image_urls

                return building_summary

    except Exception as e:
        print(f"건물 정보 조회 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="건물 정보 조회 중 오류가 발생했습니다.")

from pymysql.cursors import DictCursor

def fetch_latest_transactions(building_id: int, max_results=5):
    """
    데이터베이스에서 특정 건물의 최신 거래 정보를 가져옵니다.
    """
    try:
        with get_db_connection() as connection:
            with connection.cursor(DictCursor) as cursor:  # DictCursor 사용
                query = """
                    SELECT trade_year, trade_month, trade_day, trade_amount, trade_size, floor
                    FROM Property_Trade
                    WHERE property_id = %s
                    ORDER BY trade_year DESC, trade_month DESC, trade_day DESC
                    LIMIT %s
                """
                params = (building_id, max_results)
                cursor.execute(query, params)
                transactions = cursor.fetchall()

                if not transactions:
                    return {"message": "최근 거래 내역이 없습니다."}

                # 데이터 변환
                latest_transactions = []
                for transaction in transactions:
                    formatted_date = f"{transaction['trade_year']}.{int(transaction['trade_month']):02}.{int(transaction['trade_day']):02}"
                    trade_amount_billion = int(transaction['trade_amount']) / 10000

                    latest_transactions.append({
                        "계약일자": formatted_date,
                        "거래금액": trade_amount_billion,
                        "전용면적": transaction["trade_size"],
                        "층": transaction["floor"],
                    })

                return latest_transactions

    except Exception as e:
        print(f"거래 정보 조회 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="거래 정보 조회 중 오류가 발생했습니다.")

@router.get("/building-latest-transactions/{building_id}")
async def get_building_and_transactions(building_id: int):
    """
    건물 정보와 최신 거래 5건을 반환하는 API 엔드포인트 (GET 요청)
    """
    try:
        # 건물 정보 가져오기
        building_summary = fetch_building_info(building_id)

        # 거래 정보 가져오기
        latest_transactions = fetch_latest_transactions(building_id)

        return JSONResponse(content={
            "건물정보": building_summary,
            "최신거래": latest_transactions
        })

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
