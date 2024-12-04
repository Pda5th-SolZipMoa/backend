from fastapi import APIRouter, HTTPException, Request;
from pydantic import BaseModel
from typing import List
from fastapi.concurrency import run_in_threadpool
from core.mysql_connector import get_db_connection
from datetime import datetime
import pymysql.cursors
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import STATE_RUNNING
import asyncio
from core.jwt import extract_user_id
import logging

router = APIRouter()

# 데이터 모델
class OwnershipRequest(BaseModel):
    property_detail_id: int
    quantity: int
    tradeable_tokens: int
    buy_price: float
    subscription_end_date: datetime

class OwnershipRecord(OwnershipRequest):
    id: int
    created_at: str

@router.post("/subscribe", response_model=OwnershipRecord)
async def subscribe(request: OwnershipRequest, jwt: Request):
    """
    Subscriptions 테이블에 청약 데이터를 추가하고 사용자의 주문 가능 금액과 보유 금액을 감소
    """
    # 쿠키에서 JWT 가져오기
    token = jwt.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="쿠키에 JWT없음")

    # JWT에서 유저 ID 가져오기
    try:
        user_id = extract_user_id(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"토큰 유효 X {e}")

    total_cost = request.buy_price * request.quantity

    def check_and_update_user_balance():
        """
        사용자의 잔액을 확인하고 주문 가능 금액과 보유 금액을 감소시킴
        """
        select_query = """
            SELECT total_balance, orderable_balance
            FROM Users
            WHERE id = %s
        """
        update_query = """
            UPDATE Users
            SET total_balance = total_balance - %s,
                orderable_balance = orderable_balance - %s
            WHERE id = %s
        """
        try:
            with get_db_connection() as connection:
                with connection.cursor() as cursor:
                    # 1. 사용자 잔액 확인
                    cursor.execute(select_query, (user_id,))
                    result = cursor.fetchone()

                    # 2. 결과 데이터 검증
                    if not result or len(result) != 2:
                        raise HTTPException(status_code=404, detail="사용자 정보 없음")

                    # 3. 데이터 추출 및 타입 검증
                    total_balance, orderable_balance = result

                    if not isinstance(total_balance, int) or not isinstance(orderable_balance, int):
                        raise HTTPException(status_code=500, detail="잔액 필드의 데이터 타입 오류")

                    # 4. 잔액 비교
                    if total_balance < total_cost or orderable_balance < total_cost:
                        raise HTTPException(status_code=400, detail="잔액 부족")

                    # 5. 사용자 잔액 업데이트
                    cursor.execute(update_query, (total_cost, total_cost, user_id))
                    connection.commit()

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"잔액 업데이트 실패: {e}")

    def insert_subscription():
        """
        Subscriptions 테이블에 청약 데이터 삽입
        """
        query = """
            INSERT INTO Subscriptions (user_id, property_detail_id, price_per_token, quantity, status, subscription_end_date)
            VALUES (%s, %s, %s, %s, 'pending', %s)
        """
        values = (
            user_id,
            request.property_detail_id,
            request.buy_price,
            request.quantity,
            request.subscription_end_date,
        )
        try:
            with get_db_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, values)
                    connection.commit()
                    return cursor.lastrowid
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database insertion failed: {e}")

    try:
        # 1. 사용자 잔액 확인 및 업데이트
        await run_in_threadpool(check_and_update_user_balance)

        # 2. 청약 데이터 삽입
        subscription_id = await run_in_threadpool(insert_subscription)

        # 3. 응답 반환
        return OwnershipRecord(
            id=subscription_id,
            property_detail_id=request.property_detail_id,
            quantity=request.quantity,
            tradeable_tokens=request.tradeable_tokens,
            buy_price=request.buy_price,
            subscription_end_date=request.subscription_end_date,
            created_at="NOW()",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 특정 청약 토큰에서 청약이 완료된 토큰 합산하여 반환
@router.get("/tokens/{property_detail_id}")
async def get_total_quantity(property_detail_id: int):
    """
    특정 property_detail_id에 해당하는 모든 quantity 합산 반환
    """
    def fetch_total_quantity():
        query = """
            SELECT SUM(quantity) AS total_quantity
            FROM Subscriptions
            WHERE property_detail_id = %s
        """
        try:
            with get_db_connection() as connection:
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(query, (property_detail_id,))
                    result = cursor.fetchone()
                    if result and result['total_quantity'] is not None:
                        return result['total_quantity']
                    return 0
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    total_quantity = await run_in_threadpool(fetch_total_quantity)
    return {"property_detail_id": property_detail_id, "total_quantity": total_quantity}

# 사용자 id를 기준으로 청약된 테이블 조회 
@router.get("/subscriptions")
async def get_subscriptions(request: Request):
     # 쿠키에서 JWT 가져오기
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="쿠키에 JWT없음")

    # JWT에서 유저 ID 가져오기
    try:
        user_id = extract_user_id(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"토큰 유효 X {e}")
    """
    특정 사용자 ID를 기준으로 Subscriptions 테이블 조회
    """
    query = """
        SELECT 
            s.id,
            s.price_per_token, 
            s.quantity, 
            s.status, 
            s.created_at,
            pd.detail_floor,
            b.name AS building_name
        FROM Subscriptions s
        LEFT JOIN Property_Detail pd ON s.property_detail_id = pd.id
        LEFT JOIN Properties b ON pd.property_id = b.id
        WHERE s.user_id = %s 
        ORDER BY s.created_at DESC
    """
    try:
        with get_db_connection() as connection:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # user_id만으로 조회
                cursor.execute(query, (user_id))
                subscriptions = cursor.fetchall()
                return {"subscriptions": subscriptions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

# 로그 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 스케줄러 초기화
scheduler = BackgroundScheduler()
async def move_subscriptions_to_ownerships(interval: int = 60):
    """
    주기적으로 Subscriptions 데이터를 확인하고 Ownerships로 이동하며, Property_Detail 상태를 업데이트.
    """
    while True:
        try:
            logging.info("Checking for subscriptions to move to ownerships...")
            with get_db_connection() as connection:
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    # 1. 'pending' 상태의 청약 데이터를 조회
                    query_select = """
                        SELECT s.id AS subscription_id, s.user_id, s.property_detail_id, s.quantity, s.price_per_token,
                               pd.subscription_status
                        FROM Subscriptions s
                        JOIN Property_Detail pd ON s.property_detail_id = pd.id
                        WHERE s.subscription_end_date <= NOW() 
                          AND s.status = 'pending'
                          AND pd.subscription_status = 'pending'
                    """
                    cursor.execute(query_select)
                    subscriptions = cursor.fetchall()

                    if not subscriptions:
                        logging.info("No subscriptions to process.")
                    else:
                        for subscription in subscriptions:
                            try:
                                # 2. Ownerships 테이블로 데이터 이동
                                query_insert = """
                                    INSERT INTO Ownerships (user_id, property_detail_id, quantity, tradeable_tokens, buy_price, created_at)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """
                                cursor.execute(
                                    query_insert,
                                    (
                                        subscription['user_id'],
                                        subscription['property_detail_id'],
                                        subscription['quantity'],
                                        subscription['quantity'],  # tradeable_tokens
                                        subscription['price_per_token'],
                                        datetime.now(),  # Python에서 현재 시간 추가
                                    ),
                                )

                                # 3. Subscriptions 상태 업데이트
                                query_update_subscription = """
                                    UPDATE Subscriptions
                                    SET status = 'fulfilled'
                                    WHERE id = %s
                                """
                                cursor.execute(query_update_subscription, (subscription['subscription_id'],))

                                # 4. Property_Detail 상태 업데이트
                                query_update_property = """
                                    UPDATE Property_Detail
                                    SET subscription_status = 'fulfilled'
                                    WHERE id = %s
                                """
                                cursor.execute(query_update_property, (subscription['property_detail_id'],))

                                logging.info(f"Processed subscription ID: {subscription['subscription_id']}")
                            except Exception as e:
                                logging.error(f"Error processing subscription ID {subscription['subscription_id']}: {e}")
                                continue

                        # 5. 변경사항 커밋
                        connection.commit()
                        logging.info("All subscriptions processed successfully.")
        except Exception as e:
            logging.error(f"Error in move_subscriptions_to_ownerships: {e}")

        # 6. 주기적으로 실행
        await asyncio.sleep(interval)