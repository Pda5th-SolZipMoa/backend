import os
from dotenv import load_dotenv
import redis

# .env 파일 로드
load_dotenv()
print(os.getenv("DB_HOST"))
# MySQL 설정
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "charset": os.getenv("DB_CHARSET"),
}

# Redis 설정
REDIS_CLIENT = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    db=int(os.getenv("REDIS_DB")),
    decode_responses=True,
)

# 기타 설정 (예: JWT)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "defaultsecretkey")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
