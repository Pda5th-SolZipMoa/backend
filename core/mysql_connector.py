from typing import Annotated, TYPE_CHECKING
import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager, asynccontextmanager
from dotenv import load_dotenv
import os
from fastapi import Depends

if TYPE_CHECKING:
    from pymysql import Connection


# .env 파일 로드
load_dotenv()

# 환경 변수에서 데이터베이스 설정 불러오기
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME"),
    'charset': os.getenv("DB_CHARSET"),
    'cursorclass': DictCursor
}

# 데이터베이스 연결 생성

# Seperate function using Depends or using with clause


@contextmanager
def get_db_connection():
    # no qa -> Needs test
    # return get_db()
    yield get_db()


def get_db():
    connection = pymysql.connect(**DB_CONFIG)

    try:
        yield connection
    finally:
        connection.close()


DB = Annotated["Connection", Depends(get_db)]
