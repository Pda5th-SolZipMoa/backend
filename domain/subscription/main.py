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




