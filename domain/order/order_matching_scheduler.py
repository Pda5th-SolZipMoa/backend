import asyncio
import json
from datetime import datetime
import pymysql
from core.settings import REDIS_CLIENT, DB_CONFIG
from core.redis import update_order_book_in_redis

def match_orders(property_id: int):
    # 1. 호가창 정보 가져오기
    redis_key = f"order_book:{property_id}"
    order_book_data = REDIS_CLIENT.hget(redis_key, "order_book")

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 2. 호가창에 주문이 없을 경우
        if not order_book_data:
            print(f"[{datetime.now()}] 호가창에 주문이 없음: property_id={property_id}")
            save_previous_record_if_needed(cursor, property_id)
            conn.commit()
            return

        order_book = json.loads(order_book_data)
        buy_orders = order_book.get("buy", {})
        sell_orders = order_book.get("sell", {})

        # 3. 단일가 찾기
        print(f"[{datetime.now()}] 단일가 매매 실행: property_id={property_id}")
        max_traded_price, max_quantity = find_single_price(buy_orders, sell_orders)

        # 3-1. 단일가 매칭이 없는 경우
        if max_traded_price is None:
            print(f"[{datetime.now()}] 매칭 가능한 단일가가 없음: property_id={property_id}")
            save_previous_record_if_needed(cursor, property_id)
            conn.commit()
            return

        print(f"[{datetime.now()}] property_id={property_id} 단일가: {max_traded_price}")

        max_traded_price = int(max_traded_price)

        # 4. 단일가 이상/이하 주문 필터링 및 정렬
        sell_prices = sorted(
            [price for price in sell_orders.keys() if int(price) <= int(max_traded_price)]
        )  # 낮은 가격 우선
        buy_prices = sorted(
            [price for price in buy_orders.keys() if int(price) >= int(max_traded_price)],
            reverse=True
        )  # 높은 가격 우선

        # 5. 매칭 실행
        for sell_price in sell_prices:
            for buy_price in buy_prices:
                sell_orders_at_price = sell_orders[sell_price]
                buy_orders_at_price = buy_orders[buy_price]

                while sell_orders_at_price and buy_orders_at_price:
                    sell_order = sell_orders_at_price[0]  # FIFO: 첫 번째 매도 주문
                    buy_order = buy_orders_at_price[0]  # FIFO: 첫 번째 매수 주문

                    matched_quantity = min(sell_order["quantity"], buy_order["quantity"])
                    total_transaction_value = matched_quantity * max_traded_price

                    # 5-1. 매수자 정보 조회
                    cursor.execute("""
                        SELECT user_id, price_per_token
                        FROM Order_Archive
                        WHERE id = %s
                    """, (buy_order["order_id"],))
                    buy_order_details = cursor.fetchone()
                    buy_user_id, buy_price_per_token = buy_order_details

                    # 5-2. 매도자 정보 조회
                    cursor.execute("""
                        SELECT user_id
                        FROM Order_Archive
                        WHERE id = %s
                    """, (sell_order["order_id"],))
                    sell_order_details = cursor.fetchone()
                    sell_user_id = sell_order_details[0]

                    # 5-3. 매수자 업데이트
                    refund_amount = (buy_price_per_token - int(max_traded_price)) * matched_quantity
                    cursor.execute("""
                        UPDATE Users
                        SET total_balance = total_balance - %s,
                            orderable_balance = orderable_balance + %s
                        WHERE id = %s
                    """, (total_transaction_value, refund_amount, buy_user_id))

                    # 매수자 소유권 업데이트: 존재 여부 확인
                    cursor.execute("""
                        SELECT quantity, tradeable_tokens, buy_price
                        FROM Ownerships
                        WHERE user_id = %s AND property_detail_id = %s
                    """, (buy_user_id, property_id))
                    ownership = cursor.fetchone()

                    if ownership:
                        # 기존 소유권이 있으면 UPDATE
                        existing_quantity = ownership[0]
                        existing_buy_price = ownership[2]

                        # 가중 평균 계산: 새로운 평단가
                        total_quantity = existing_quantity + matched_quantity
                        new_buy_price = (
                                                (existing_quantity * existing_buy_price) + (
                                                    matched_quantity * max_traded_price)
                                        ) / total_quantity

                        cursor.execute("""
                            UPDATE Ownerships
                            SET quantity = quantity + %s,
                                tradeable_tokens = tradeable_tokens + %s,
                                buy_price = %s
                            WHERE user_id = %s AND property_detail_id = %s
                        """, (matched_quantity, matched_quantity, new_buy_price, buy_user_id, property_id))
                    else:
                        # 기존 소유권이 없으면 INSERT
                        cursor.execute("""
                            INSERT INTO Ownerships (user_id, property_detail_id, quantity, tradeable_tokens, buy_price, created_at)
                            VALUES (%s, %s, %s, %s, %s, NOW())
                        """, (buy_user_id, property_id, matched_quantity, matched_quantity, max_traded_price))

                    # 5-4. 매도자 업데이트
                    cursor.execute("""
                        UPDATE Users
                        SET total_balance = total_balance + %s,
                            orderable_balance = orderable_balance + %s
                        WHERE id = %s
                    """, (total_transaction_value, total_transaction_value, sell_user_id))

                    # 매도자 소유권 업데이트: 남은 수량 확인
                    cursor.execute("""
                        SELECT quantity
                        FROM Ownerships
                        WHERE user_id = %s AND property_detail_id = %s
                    """, (sell_user_id, property_id))
                    sell_ownership = cursor.fetchone()

                    if sell_ownership:
                        remaining_quantity = sell_ownership[0] - matched_quantity
                        if remaining_quantity > 0:
                            # 남은 소유량 업데이트
                            cursor.execute("""
                                UPDATE Ownerships
                                SET quantity = %s
                                WHERE user_id = %s AND property_detail_id = %s
                            """, (remaining_quantity, sell_user_id, property_id))
                        else:
                            # 남은 소유량이 0이면 소유권 삭제
                            cursor.execute("""
                                DELETE FROM Ownerships
                                WHERE user_id = %s AND property_detail_id = %s
                            """, (sell_user_id, property_id))

                    # 5-5. 체결된 주문 새로 생성 (매수자)
                    cursor.execute("""
                        INSERT INTO Order_Archive (property_detail_id, user_id, order_type, price_per_token, quantity, status, created_at)
                        SELECT property_detail_id, user_id, 'buy', %s, %s, 'fulfilled', NOW()
                        FROM Order_Archive WHERE id = %s
                    """, (max_traded_price, matched_quantity, buy_order["order_id"]))

                    # 5-6. 체결된 주문 새로 생성 (매도자)
                    cursor.execute("""
                        INSERT INTO Order_Archive (property_detail_id, user_id, order_type, price_per_token, quantity, status, created_at)
                        SELECT property_detail_id, user_id, 'sell', %s, %s, 'fulfilled', NOW()
                        FROM Order_Archive WHERE id = %s
                    """, (max_traded_price, matched_quantity, sell_order["order_id"]))


                    # 5-7. 주문 수량 업데이트
                    sell_order["quantity"] -= matched_quantity
                    buy_order["quantity"] -= matched_quantity

                    if sell_order["quantity"] == 0:
                        sell_orders_at_price.pop(0)  # 매도 주문 완료 → 제거
                        cursor.execute("DELETE FROM Order_Archive WHERE id = %s", (sell_order["order_id"],))
                    else:
                        cursor.execute("""
                            UPDATE Order_Archive
                            SET quantity = %s
                            WHERE id = %s
                        """, (sell_order["quantity"], sell_order["order_id"]))
                        sell_orders[sell_price][0]["quantity"] = sell_order["quantity"]  # Redis 호가창 업데이트

                    if buy_order["quantity"] == 0:
                        buy_orders_at_price.pop(0)  # 매수 주문 완료 → 제거
                        cursor.execute("DELETE FROM Order_Archive WHERE id = %s", (buy_order["order_id"],))
                    else:
                        cursor.execute("""
                            UPDATE Order_Archive
                            SET quantity = %s
                            WHERE id = %s
                        """, (buy_order["quantity"], buy_order["order_id"]))
                        buy_orders[buy_price][0]["quantity"] = buy_order["quantity"]  # Redis 호가창 업데이트

                    conn.commit()

        # Redis 업데이트
        REDIS_CLIENT.hset(redis_key, "order_book", json.dumps(order_book))

        # 6. 체결된 단일가 기록 저장
        cursor.execute("""
            INSERT INTO Property_History (recorded_date, price, quantity, property_detail_id)
            VALUES (NOW(), %s, %s, %s)
        """, (max_traded_price, max_quantity, property_id))
        conn.commit()

        # 7. Redis Pub/Sub 메시지 발행
        update_order_book_in_redis(property_id, order_book)

    except pymysql.MySQLError as e:
        print(f"[{datetime.now()}] DB 에러: {e}")
    finally:
        cursor.close()
        conn.close()

    # 체결 내역 출력
    print(f"[{datetime.now()}] 매칭된 주문이 처리되었습니다.")

# 단일가 찾는 함수
def find_single_price(buy_orders, sell_orders):
    # 매수/매도 가격 정렬
    sorted_buy_prices = sorted(buy_orders.keys(), key=lambda x: int(x), reverse=True)  # 높은 가격 우선
    sorted_sell_prices = sorted(sell_orders.keys(), key=lambda x: int(x))  # 낮은 가격 우선

    max_traded_price = None
    max_quantity = 0

    # 단일가매매 가격 찾기
    for buy_price in sorted_buy_prices:
        buy_quantity = sum(order["quantity"] for order in buy_orders[buy_price])
        for sell_price in sorted_sell_prices:
            sell_quantity = sum(order["quantity"] for order in sell_orders[sell_price])
            if int(buy_price) >= int(sell_price):  # 매칭 가능 조건
                traded_quantity = min(buy_quantity, sell_quantity)
                if traded_quantity > max_quantity:
                    max_quantity = traded_quantity
                    max_traded_price = sell_price
            else:
                break  # 매칭 불가

    return max_traded_price, max_quantity

# 이전 기록 저장 함수
# 단일가 매칭이 없거나 호가창이 비어있는 경우 호출됩니다.
def save_previous_record_if_needed(cursor, property_id):
    print(f"[{datetime.now()}] 이전 기록 저장: property_id={property_id}")
    cursor.execute("""
        SELECT price FROM Property_History
        WHERE property_detail_id = %s
        ORDER BY recorded_date DESC LIMIT 1
    """, (property_id,))
    last_record = cursor.fetchone()

    price_to_record = last_record[0] if last_record else 0

    cursor.execute("""
        INSERT INTO Property_History (recorded_date, price, property_detail_id)
        VALUES (NOW(), %s, %s)
    """, (price_to_record, property_id))



# 단일가 매매 스케줄러
async def periodic_matching(interval: int = 300):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM Property_Detail")
        property_ids = [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

    while True:
        for property_id in property_ids:
            match_orders(property_id)
        await asyncio.sleep(interval)

# 메인 실행
if __name__ == "__main__":
    print(f"단일가 매매 스크립트 실행 중...")
    asyncio.run(periodic_matching())