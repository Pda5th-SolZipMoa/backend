from core.settings import REDIS_CLIENT
from core.websockets import manager
import asyncio
import json

# Redis Pub/Sub Listener
async def redis_listener():
    # Redis 채널 구독
    pubsub = REDIS_CLIENT.pubsub()
    pubsub.subscribe("order_book_updates")
    print("Redis listener started, subscribed to 'order_book_updates'")
    try:
        while True:
            # Redis에서 메시지 수신
            message = pubsub.get_message()
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                property_id = data.get("property_id")
                if property_id:
                    # WebSocket으로 브로드캐스트
                    await manager.broadcast(json.dumps(data), property_id)
            await asyncio.sleep(0.01)  # Redis 메시지 폴링 간격
    except Exception as e:
        print(f"Redis listener error: {e}")

# Redis 데이터 업데이트 및 Pub/Sub 메시지 발행
def update_order_book_in_redis(property_id: int, order_book: dict):
    redis_key = f"order_book:{property_id}"
    REDIS_CLIENT.hset(redis_key, "order_book", json.dumps(order_book))
    update_message = {"property_id": property_id, "order_book": order_book}
    REDIS_CLIENT.publish("order_book_updates", json.dumps(update_message))


