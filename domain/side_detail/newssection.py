import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/news")
async def get_news(query: str = Query(..., description="검색할 키워드")):
    """
    검색어에 따른 최신 뉴스 크롤링
    """
    try:
        # 다음 뉴스 검색 URL
        search_url = f"https://search.daum.net/search?w=news&q={query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }

        # 요청 보내기
        response = requests.get(search_url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="뉴스 크롤링 중 오류가 발생했습니다.")

        # HTML 파싱
        soup = BeautifulSoup(response.text, "html.parser")

        # 뉴스 기사 목록 선택
        articles = soup.select("#dnsColl > div > ul > li")

        if not articles:
            raise HTTPException(status_code=404, detail="뉴스 기사를 찾을 수 없습니다.")

        news_list = []

        # 각 기사에서 정보 추출
        for article in articles[:3]:  # 최대 3개 크롤링
            # 제목
            title_tag = article.select_one(".item-title > strong > a")
            title = title_tag.get_text(strip=True) if title_tag else "제목 없음"

            # 내용 (요약)
            content_tag = article.select_one(".item-contents > p")
            content = content_tag.get_text(
                strip=True) if content_tag else "내용 없음"

            # 이미지
            image_tag = article.select_one(".item-thumb .wrap_thumb img")
            print("image_tag", image_tag)
            if image_tag:
                # data-original-src 속성 확인
                image = image_tag.get(
                    "data-original-src") or "이미지 없음"
            else:
                image = "이미지 없음"
            # 링크
            link = title_tag["href"] if title_tag else "링크 없음"

            # 날짜
            date_tag = article.select_one(".item-contents > span > span")
            date = date_tag.get_text(strip=True) if date_tag else "날짜 없음"

            # 결과에 추가
            news_list.append({
                "title": title,
                "content": content,
                "image": image,
                "link": link,
                "date": date,
            })

        return news_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
