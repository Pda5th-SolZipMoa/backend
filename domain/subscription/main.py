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
    Subscriptions 테이블에 청약 데이터를 추가
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
        
    def insert_subscription():
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
        subscription_id = await run_in_threadpool(insert_subscription)
        return OwnershipRecord(
            id=subscription_id,
            user_id=user_id,
            property_detail_id=request.property_detail_id,
            quantity=request.quantity,
            tradeable_tokens=request.tradeable_tokens,
            buy_price=request.buy_price,
            subscription_end_date=request.subscription_end_date,
            created_at="NOW()",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


