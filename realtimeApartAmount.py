import requests
import os
from datetime import datetime, timedelta
from core.mysql_connector import get_db_connection
from pymysql.cursors import DictCursor
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()
SERVICE_KEY = os.getenv("PUBLIC_DATA_API_KEY")

# 아파트 거래 API 정보
API_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
API_KEY = SERVICE_KEY  # 데이터포털 API 키를 여기에 입력하세요


def fetch_apartment_transactions(lawd_cd, bonbun, bubun=None, max_results=5):
    """
    아파트 실거래가 API에서 거래 내역을 가져옵니다.
    """
    transactions = []
    today = datetime.now()

    # 최근 12개월 동안의 데이터를 검색
    for i in range(12):
        target_date = today - timedelta(days=i * 30)
        deal_ymd = target_date.strftime("%Y%m")  # YYYYMM 형식

        params = {
            'serviceKey': API_KEY,
            'LAWD_CD': lawd_cd,
            'DEAL_YMD': deal_ymd,
            'numOfRows': 100,
        }

        response = requests.get(API_URL, params=params)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            body = root.find('body')
            if not body or not body.find('items'):
                continue

            items = body.find('items').findall('item')

            for item in items:
                try:
                    trade_year = item.find('dealYear').text.strip() if item.find('dealYear') is not None else "Unknown"
                    trade_month = item.find('dealMonth').text.strip() if item.find('dealMonth') is not None else "Unknown"
                    trade_day = item.find('dealDay').text.strip() if item.find('dealDay') is not None else "Unknown"
                    trade_amount = (
                        item.find('dealAmount').text.replace(',', '').strip()
                        if item.find('dealAmount') is not None
                        else "0"
                    )
                    trade_size = (
                        float(item.find('excluUseAr').text.strip())
                        if item.find('excluUseAr') is not None
                        else 0.0
                    )
                    floor = (
                        int(item.find('floor').text.strip())
                        if item.find('floor') is not None
                        else 0
                    )

                    transactions.append({
                        "trade_year": trade_year,
                        "trade_month": trade_month,
                        "trade_day": trade_day,
                        "trade_amount": trade_amount,
                        "trade_size": trade_size,
                        "floor": floor,
                    })

                    # 최대 결과 수에 도달하면 반환
                    if len(transactions) >= max_results:
                        return transactions

                except Exception as e:
                    print(f"Error parsing item: {e}")
                    continue  # 오류가 발생해도 다음 데이터를 계속 처리

    return transactions


def update_property_transactions():
    """
    Properties 테이블의 모든 property_id에 대해 거래 내역을 업데이트합니다.
    """
    try:
        with get_db_connection() as connection:
            with connection.cursor(DictCursor) as cursor:
                # Properties 테이블에서 모든 property_id 가져오기
                cursor.execute("SELECT id, building_code FROM Properties")
                properties = cursor.fetchall()

                for property in properties:
                    property_id = property['id']
                    building_code = property['building_code']

                    # building_code를 파싱하여 LAWD_CD, bonbun, bubun 추출
                    lawd_cd = building_code[:5]
                    bonbun = building_code[11:15]
                    bubun = building_code[15:19] if building_code[15:19].strip() != '0' else None

                    # 최신 거래 내역 가져오기
                    latest_transactions = fetch_apartment_transactions(lawd_cd, bonbun, bubun)

                    if not latest_transactions:
                        print(f"Property ID {property_id}: No new transactions found.")
                        continue

                    # 기존 거래 데이터 확인
                    cursor.execute("SELECT COUNT(*) AS cnt FROM Property_Trade WHERE property_id = %s", (property_id,))
                    existing_count = cursor.fetchone()['cnt']

                    if existing_count > 0:
                        # 기존 거래 데이터 삭제 및 새로운 데이터 삽입
                        cursor.execute("DELETE FROM Property_Trade WHERE property_id = %s", (property_id,))
                        print(f"Property ID {property_id}: Existing transactions deleted.")

                    # 새로운 거래 데이터 삽입
                    for transaction in latest_transactions:
                        insert_query = """
                            INSERT INTO Property_Trade (
                                property_id, trade_year, trade_month, trade_day, trade_amount, trade_size, floor
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(insert_query, (
                            property_id,
                            transaction["trade_year"],
                            transaction["trade_month"],
                            transaction["trade_day"],
                            transaction["trade_amount"],
                            transaction["trade_size"],
                            transaction["floor"]
                        ))
                    connection.commit()
                    print(f"Property ID {property_id}: Transactions updated successfully.")

    except Exception as e:
        print(f"Error updating property transactions: {str(e)}")


if __name__ == "__main__":
    print(f"Starting transaction update at {datetime.now()}")
    update_property_transactions()
    print(f"Transaction update completed at {datetime.now()}")
