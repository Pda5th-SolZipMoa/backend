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



# 스케줄러 초기화
scheduler = BackgroundScheduler()

from datetime import datetime

def move_subscriptions_to_ownerships():
    """
    청약 종료일에 도달한 데이터 중 'pending' 상태인 항목만 Ownerships 테이블로 이동
    """
    query_select = """
        SELECT id, user_id, property_detail_id, quantity, price_per_token
        FROM Subscriptions
        WHERE subscription_end_date <= NOW() AND status = 'pending'
    """
    query_insert = """
        INSERT INTO Ownerships (user_id, property_detail_id, quantity, tradeable_tokens, buy_price, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    query_update = """
        UPDATE Subscriptions
        SET status = 'fulfilled'
        WHERE id = %s
    """
    try:
        with get_db_connection() as connection:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 1. 청약 종료일에 도달하고 상태가 'pending'인 데이터 조회
                cursor.execute(query_select)
                subscriptions = cursor.fetchall()

                print(f"Found {len(subscriptions)} subscriptions to process.")  # 로그 출력

                for subscription in subscriptions:
                    try:
                        # 2. Ownerships 테이블로 데이터 이동
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
                        # 3. Subscriptions 테이블 상태 업데이트
                        cursor.execute(query_update, (subscription['id'],))
                        print(f"Processed subscription ID: {subscription['id']}")  # 로그 출력
                    except Exception as e:
                        print(f"Error processing subscription ID {subscription['id']}: {e}")
                        continue

                # 4. 변경사항 커밋
                connection.commit()
    except Exception as e:
        print(f"Error moving subscriptions to ownerships: {e}")


# 스케줄러 작업 추가
if not scheduler.get_jobs():
    scheduler.add_job(move_subscriptions_to_ownerships, 'interval', hours=24)  

@router.on_event("startup")
async def startup_event():
    """
    FastAPI 앱 시작 시 스케줄러를 시작
    """
    if scheduler.state != STATE_RUNNING:  
        scheduler.start()

@router.on_event("shutdown")
async def shutdown_event():
    """
    FastAPI 앱 종료 시 스케줄러를 종료
    """
    if scheduler.state == STATE_RUNNING:
        scheduler.shutdown()