import asyncio
import json
import redis
from datetime import datetime
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Redis 설정
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    db=int(os.getenv("REDIS_DB")),
    decode_responses=True
)


# 단일가 매매 함수
def match_orders(property_id: int):
    redis_key = f"order_book:{property_id}"
    order_book_data = redis_client.hget(redis_key, "order_book")

    if not order_book_data:
        print(f"[{datetime.now()}] 호가창에 주문이 없습니다.")
        return

    # 호가창 데이터 로드
    order_book = json.loads(order_book_data)
    buy_orders = order_book.get("buy", {})
    sell_orders = order_book.get("sell", {})

    print(f"[{datetime.now()}] 단일가 매매 실행: property_id={property_id}")

    # 매수/매도 가격 정렬
    sorted_buy_prices = sorted(buy_orders.keys(), key=lambda x: int(x), reverse=True)  # 높은 가격 우선
    sorted_sell_prices = sorted(sell_orders.keys(), key=lambda x: int(x))  # 낮은 가격 우선

    trades = []  # 체결 내역

    # 매칭 로직
    while sorted_buy_prices and sorted_sell_prices:
        highest_buy_price = int(sorted_buy_prices[0])
        lowest_sell_price = int(sorted_sell_prices[0])

        if highest_buy_price >= lowest_sell_price:  # 매칭 조건
            buy_orders_at_price = buy_orders[str(highest_buy_price)]
            sell_orders_at_price = sell_orders[str(lowest_sell_price)]

            buy_order = buy_orders_at_price[0]  # FIFO 방식
            sell_order = sell_orders_at_price[0]

            matched_quantity = min(buy_order["quantity"], sell_order["quantity"])

            # 체결 기록
            trades.append({
                "price": lowest_sell_price,
                "quantity": matched_quantity,
                "buy_order_id": buy_order["order_id"],
                "sell_order_id": sell_order["order_id"]
            })

            # 주문 수량 업데이트
            buy_order["quantity"] -= matched_quantity
            sell_order["quantity"] -= matched_quantity

            # 완료된 주문 제거
            if buy_order["quantity"] == 0:
                buy_orders_at_price.pop(0)
                if not buy_orders_at_price:
                    del buy_orders[str(highest_buy_price)]
                    sorted_buy_prices.pop(0)

            if sell_order["quantity"] == 0:
                sell_orders_at_price.pop(0)
                if not sell_orders_at_price:
                    del sell_orders[str(lowest_sell_price)]
                    sorted_sell_prices.pop(0)

        else:
            break  # 매칭 불가 상태

    # Redis 호가창 업데이트
    order_book["buy"] = buy_orders
    order_book["sell"] = sell_orders
    redis_client.hset(redis_key, "order_book", json.dumps(order_book))

    # 매칭 결과 출력
    if trades:
        print(f"[{datetime.now()}] 체결 내역:")
        for trade in trades:
            print(trade)
    else:
        print(f"[{datetime.now()}] 매칭된 주문이 없습니다.")


# 단일가 매매 스케줄러
async def periodic_matching(interval: int = 300):
    while True:
        #match_orders(property_id)
        match_orders(5)
        await asyncio.sleep(interval)


# 메인 실행
if __name__ == "__main__":
    property_id = 6  # 특정 property_id 설정
    print(f"단일가 매매 스크립트 실행 중... property_id={property_id}")
    asyncio.run(periodic_matching(property_id))