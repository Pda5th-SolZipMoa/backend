from fastapi import HTTPException, APIRouter, Response
from pydantic import BaseModel
from core.jwt import create_access_token
from core.settings import DB_CONFIG
import pymysql

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
def signup(user: User):
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

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
                INSERT INTO Users (username, phone, total_balance, orderable_balance) VALUES (%s, %s, %s, %s)
            '''
            cursor.execute(sql, (user.name, user.phone, 100000000, 100000000))
            conn.commit()
        return {"message": "Signup successful"}
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB Error: {e}")
    finally:
        cursor.close()
        conn.close()


# 로그인 API
@router.post("/login")
def login(login_request: LoginRequest, response: Response):
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

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
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"DB Error: {e}")
    finally:
        cursor.close()
        conn.close()