from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# from domain.apartments.getApartments import router as apartments_router
# from domain.apartments.getBuildInfo import router as building_router
from domain.apartments.getTotalApartInfo import router as total_router
from domain.apartments.saveForm import router as form_router
from domain.user.login import router as auth_router
from domain.user.user_order_balance_api import router as order_balance_router
from domain.order.main import router as order_router
from domain.order.order_cancel import router as order_cancel_router
from domain.order.order_socket import router as order_socket_router
from domain.order.order_matching_scheduler import periodic_matching
from domain.buildings.main import router as buildings_router
from domain.properties.property_history import router as property_history_router
from domain.archives.archives import router as archives_router
from core.redis import redis_listener
import asyncio
import requests
import os

from pydantic import BaseModel
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 허용할 도메인 (프론트엔드 주소)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

# 각 도메인의 라우터를 등록 예시
# app.include_router(my_page_router.router, prefix="/api/mypage", tags=["mypage"])
app.include_router(total_router,prefix="/api",tags=["apartments"])
app.include_router(form_router,prefix="/api",tags=["apartments"])
app.include_router(buildings_router, prefix="/api", tags=["buildings"])


app.include_router(auth_router, prefix='/api',
                   tags=['auth'])

app.include_router(order_router, prefix="/api/orders", tags=["order"])
app.include_router(order_cancel_router, prefix="/api/orders", tags=["order_cancel"])
app.include_router(order_socket_router, prefix="/api/ws/orders", tags=["order_socket"])

app.include_router(property_history_router, prefix="/api/properties", tags=["property_history_router"])
app.include_router(order_balance_router, prefix="/api/users", tags=["order_balance_router"])

app.include_router(archives_router, prefix="/api/order_archives", tags=["archives_router"])

# 애플리케이션 시작 시 Redis Listener와 스케줄러 실행
@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    # Redis Listener 실행
    loop.create_task(redis_listener())
    # 스케줄러 실행
    loop.create_task(periodic_matching(interval=300))


@app.get("/")
async def root():
    return {"message": "Hello, FastAPI!"}

# swagger http://127.0.0.1:8000/docs


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
