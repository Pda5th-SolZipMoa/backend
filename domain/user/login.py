from fastapi import APIRouter, HTTPException, Response
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

# 데이터베이스 시뮬레이션
fake_db = []

# Pydantic 모델


class User(BaseModel):
    name: str
    phone: str
    # created_at: datetime = datetime.now()


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
    print(db_conn)
    cursor = db_conn.cursor()
    sql = f'''
            INSERT INTO Users (username, phone) VALUES('{user.name}', '{user.phone}')
        '''
    cursor.execute(sql)
    db_conn.commit()


# 로그인 API


@router.post("/login")
def login(login_request: LoginRequest, db_conn: DB, response: Response):
    cursor = db_conn.cursor()

    # 올바른 SELECT SQL 쿼리
    sql = f'''
        SELECT username, phone FROM Users WHERE `phone`=%s
    '''
    cursor.execute(sql, (login_request.phone))
    db_user = cursor.fetchone()  # 일치하는 사용자 데이터 가져오기

    if db_user:
        # 전화번호 일치 여부 확인
        # if pwd_context.verify(login_request.phone, db_user["phone"]):
        access_token = create_access_token(
            data={"sub": db_user["username"]}
        )
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax",
        )
        return {"message": "Login successful", "user": {"username": db_user["username"]}}

    # 일치하는 데이터가 없을 경우
    raise HTTPException(status_code=400, detail="Invalid phone number")
