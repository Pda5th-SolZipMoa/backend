from fastapi import HTTPException, APIRouter, Response
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt

from core.mysql_connector import DB

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
def signup(user: User, db_conn: DB):
    cursor = db_conn.cursor()

    # 중복 체크 쿼리
    check_phone_query = '''
        SELECT phone FROM Users WHERE phone = %s
    '''
    cursor.execute(check_phone_query, (user.phone,))
    result = cursor.fetchone()

    if result:  # 중복값이 존재할 경우
        raise HTTPException(
            status_code=400, detail="This phone number is already registered.")
    else:  # 중복값이 없을 경우
        sql = '''
            INSERT INTO Users (username, phone) VALUES (%s, %s)
        '''
        cursor.execute(sql, (user.name, user.phone))
        db_conn.commit()

    return {"message": "Signup successful"}


# 로그인 API
@router.post("/login")
def login(login_request: LoginRequest, db_conn: DB, response: Response):
    cursor = db_conn.cursor()

    # 입력된 phone의 사용자 데이터 확인
    check_user_query = '''
        SELECT username, phone FROM Users WHERE phone = %s
    '''
    cursor.execute(check_user_query, (login_request.phone,))
    db_user = cursor.fetchone()

    if db_user:
        # 로그인 성공 시 토큰 생성
        access_token = create_access_token(data={"sub": db_user["username"]})
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax",
        )
        return {"message": "Login successful!", "user": {"username": db_user["username"]}}
    else:
        # 번호가 존재하지 않을 경우 기존 로직 수행
        raise HTTPException(status_code=400, detail="Invalid phone number")
