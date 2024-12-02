from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
import openai
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# OpenAI API 키 설정 (환경 변수에서 가져오기)
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()
# 데이터베이스 연결 설정
DATABASE_URL = "sqlite:///./test.db"  # 예: SQLite DB URL (환경에 맞게 변경)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

# Properties 테이블 정의
properties_table = Table("Properties", metadata, autoload_with=engine)

# 데이터 모델 정의


class ChatGPTResponse(BaseModel):
    building_info: str
    investment_info: str
    investment_strategy: str

# ChatGPT 요청 함수


def fetch_chatgpt_response(question: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": question}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"ChatGPT API 호출 오류: {str(e)}")

# API 엔드포인트: 건물명에 대한 정보 생성


@app.get("/api/building-info/{name}", response_model=ChatGPTResponse)
async def get_building_info(name: str):
    # 데이터베이스 연결
    db = SessionLocal()
    try:
        # Properties 테이블에서 건물명 검색
        query = properties_table.select().where(properties_table.c.name == name)
        result = db.execute(query).fetchone()

        if not result:
            raise HTTPException(
                status_code=404, detail="해당 이름의 건물을 찾을 수 없습니다.")

        # ChatGPT에게 질문 정의
        building_info_question = f"건물 정보에 대해 알려주세요. 건물명: {name}"
        investment_info_question = f"해당 건물의 투자 정보에 대해 설명해주세요. 건물명: {name}"
        investment_strategy_question = f"이 건물에 대한 향후 투자 전략을 제안해주세요. 건물명: {name}"

        # ChatGPT API 호출
        building_info = fetch_chatgpt_response(building_info_question)
        investment_info = fetch_chatgpt_response(investment_info_question)
        investment_strategy = fetch_chatgpt_response(
            investment_strategy_question)

        # 응답 생성
        return ChatGPTResponse(
            building_info=building_info,
            investment_info=investment_info,
            investment_strategy=investment_strategy
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
    finally:
        db.close()
