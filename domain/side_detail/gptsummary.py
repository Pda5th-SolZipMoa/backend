from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# OpenAI API 키 설정 (환경 변수에서 가져오기)
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

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
            status_code=500, detail=f"ChatGPT API 호출 오류: {str(e)}"
        )

# ChatGPT API를 호출하는 엔드포인트


@app.post("/api/chat")
async def chat_with_gpt(request: dict):
    user_message = request.get("user_message")
    if not user_message:
        raise HTTPException(status_code=400, detail="user_message 필드가 필요합니다.")
    try:
        bot_reply = fetch_chatgpt_response(user_message)
        return {"bot_reply": bot_reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
