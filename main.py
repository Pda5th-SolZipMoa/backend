from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# from domain.apartments.getApartments import router as apartments_router
# from domain.apartments.getBuildInfo import router as building_router
from starlette.staticfiles import StaticFiles
from domain.apartments.getTotalApartInfo import router as total_router
from domain.apartments.saveForm import router as form_router
from domain.apartments.getBuildingInfo import router as info_router
from domain.user.login import router as auth_router
import requests
import os

from pydantic import BaseModel
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
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
app.include_router(info_router,prefix="/api",tags=["apartments"])

app.include_router(auth_router, prefix='/api',
                   tags=['auth'])


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
