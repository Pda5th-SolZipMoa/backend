from fastapi import HTTPException, APIRouter, Response
from pydantic import BaseModel
from core.jwt import create_access_token
from core.mysql_connector import DB

# 라우터 초기화
router = APIRouter()

# Pydantic 모델
class User(BaseModel):
    name: str
    phone: str


class LoginRequest(BaseModel):
    phone: str


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
        SELECT id FROM Users WHERE phone = %s
    '''
    cursor.execute(check_user_query, (login_request.phone,))
    db_user = cursor.fetchone()

    if db_user:
        # 로그인 성공 시 토큰 생성
        access_token = create_access_token(user_id=db_user["id"])
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=30 * 60,  # 30분 (JWT 기본 만료 시간)
            samesite="lax",
        )
        return {"message": "Login successful!", "user": {"id": db_user["id"]}}
    else:
        # 번호가 존재하지 않을 경우 기존 로직 수행
        raise HTTPException(status_code=400, detail="Invalid phone number")