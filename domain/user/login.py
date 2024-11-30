from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
from core.mysql_connector import get_db_connection  # mysql_connector에서 get_db_connection 임포트

# JWT 및 비밀번호 설정
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 라우터 초기화
router = APIRouter()

# Pydantic 모델
class User(BaseModel):
    name: str
    phone: str

class LoginRequest(BaseModel):
    phone: str

# JWT 토큰 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 회원가입 API
@router.post("/signup")
def signup(user: User):
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            # 사용자 데이터 삽입
            sql = "INSERT INTO Users (username, phone) VALUES (%s, %s)"
            cursor.execute(sql, (user.name, user.phone))
            connection.commit()
            return {"message": "User registered successfully"}
        except Exception as e:
            connection.rollback()
            print("Error during user registration:", e)
            raise HTTPException(status_code=500, detail="Failed to register user")
        finally:
            cursor.close()

# 로그인 API
@router.post("/login")
def login(login_request: LoginRequest, response: Response):
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            # 사용자 데이터 조회
            sql = "SELECT username, phone FROM Users WHERE phone = %s"
            cursor.execute(sql, (login_request.phone,))
            db_user = cursor.fetchone()

            if db_user:
                # JWT 토큰 생성 및 쿠키 설정
                access_token = create_access_token(data={"sub": db_user["username"]})
                response.set_cookie(
                    key="access_token",
                    value=f"Bearer {access_token}",
                    httponly=True,
                    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    samesite="lax",
                )
                return {"message": "Login successful", "user": {"username": db_user["username"]}}
            else:
                raise HTTPException(status_code=400, detail="Invalid phone number")
        except Exception as e:
            print("Error during login:", e)
            raise HTTPException(status_code=500, detail="Failed to login")
        finally:
            cursor.close()
