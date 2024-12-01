import os
from datetime import datetime, timedelta
import jwt
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# JWT 설정 로드
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))


def create_access_token(user_id: int, expires_delta: timedelta = None) -> str:
    """
    JWT 토큰 생성 함수.

    Args:
        user_id (int): 유저 ID (Primary Key).
        expires_delta (timedelta, optional): 토큰 만료 기간. 기본값은 ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        str: 생성된 JWT.
    """
    to_encode = {"sub": str(user_id)}
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def extract_user_id(token: str) -> int:
    """
    JWT에서 유저 ID를 추출하는 함수.

    Args:
        token (str): JWT 토큰.

    Returns:
        int: 추출된 유저 ID.

    Raises:
        jwt.PyJWTError: 토큰 디코딩 실패 또는 만료된 토큰.
        ValueError: 토큰에서 ID가 발견되지 않을 경우.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("Token does not contain user ID")
        return int(user_id)
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.PyJWTError as e:
        raise ValueError(f"Token decoding error: {str(e)}")