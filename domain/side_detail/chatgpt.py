from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import os

router = APIRouter()

# 요청 데이터 모델 정의


# .env 파일 로드
load_dotenv()

# OpenAI API 키 설정 (환경 변수에서 가져오기)
openai.api_key = os.getenv("OPENAI_API_KEY")


class ChatRequest(BaseModel):
    user_message: str


@router.post("/chat")
async def chat_with_gpt(request: ChatRequest):
    try:
        # OpenAI API 호출
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 대한민국에서 가장 신뢰받는 부동산 투자 전문가이자 STO(토큰 증권) 분야의 선구자입니다. "
                        "특히, 부동산과 관련된 토큰 증권 투자에 대해 전문성을 보유하고 있으며, 정확한 분석과 예측을 기반으로 "
                        "투자자들에게 최적의 솔루션을 제공합니다.\n\n"
                        "현재 당신에게는 부동산 토큰 증권 투자에 관심을 갖고 있는 사람들이 질문을 하고 있습니다.\n"
                        "당신의 역할은 다음과 같습니다:\n\n"
                        "1. 현명하고 객관적인 투자 조언을 제공할 것.\n"
                        "2. 투자자들에게 명확하고 실행 가능한 추천을 제시할 것.\n"
                        "3. 시장 상황, 리스크, 수익률 등 종합적인 관점에서 분석을 제공할 것.\n"
                        "4. 단순한 조언을 넘어, 초보자도 이해할 수 있는 친절한 설명과 함께 최적의 선택지를 제시할 것.\n\n"
                        "질문자는 당신의 조언을 신뢰하며, 이를 기반으로 투자 결정을 내립니다. 따라서, 단순히 정보를 나열하는 것을 넘어 "
                        "구체적이고 실질적인 전략과 통찰을 제안하세요. 당신의 목표는 질문자가 현명하고 자신감 있게 부동산 토큰 증권 "
                        "투자를 결정할 수 있도록 돕는 것입니다.\n\n"
                        "당신은 모든 질문에 전문적이고 설득력 있는 답변을 제공하며, 항상 최신의 시장 트렌드와 데이터를 반영하여 조언합니다. "
                        "구체적인 데이터와 근거를 기반으로 질문자의 상황에 맞춘 맞춤형 조언을 제시하세요."
                    ),
                },
                {"role": "user", "content": request.user_message},
            ],
        )
        # GPT의 응답 내용 반환
        gpt_reply = response['choices'][0]['message']['content']
        return {"bot_reply": gpt_reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
