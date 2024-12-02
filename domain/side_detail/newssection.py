# from fastapi import APIRouter, HTTPException
# from fastapi.responses import RedirectResponse
# from bs4 import BeautifulSoup
# import requests

# router = APIRouter()


# @router.get("/news")
# async def get_news():
#     """
#     다음 뉴스에서 '서울숲 트리마제' 관련 최신 뉴스 3개 크롤링
#     """
#     try:
#         # 다음 뉴스 검색 URL
#         search_url = "https://search.daum.net/search?w=news&q=청계벽산아파트"
#         headers = {
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
#         }

#         # 요청 보내기
#         response = requests.get(search_url, headers=headers)
#         if response.status_code != 200:
#             raise HTTPException(status_code=500, detail="뉴스 크롤링 중 오류가 발생했습니다.")

#         # HTML 파싱
#         soup = BeautifulSoup(response.text, "html.parser")
#         # print(soup.prettify())  # 디버깅용: HTML 확인

#         # 선택자 수정
#         articles = soup.select(
#             "#dnsColl > div:nth-child(1) > ul > li")  # 제목이 포함된 선택자로 변경

#         # articles = soup.select(
#         #     "txt_info")

#         print(articles)

#         if not articles:
#             raise HTTPException(status_code=404, detail="뉴스 기사를 찾을 수 없습니다.")

#         news_list = []
#         for article in articles[:3]:  # 최대 3개
#             title = article.get_text(strip=True)  # 기사 제목
#             link = article.find("a")["href"]  # 기사 링크

#             # 결과에 추가
#             news_list.append({
#                 "title": title,
#                 "link": link,
#             })

#         return news_list

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# 일교 추가

# from fastapi import APIRouter, HTTPException
# from bs4 import BeautifulSoup
# import requests

# router = APIRouter()


# @router.get("/news")
# async def get_news():
#     """
#     다음 뉴스에서 관련 최신 뉴스 크롤링
#     """
#     try:
#         # 다음 뉴스 검색 URL
#         search_url = "https://search.daum.net/search?w=news&q=청계벽산아파트"
#         headers = {
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
#         }

#         # 요청 보내기
#         response = requests.get(search_url, headers=headers)
#         if response.status_code != 200:
#             raise HTTPException(status_code=500, detail="뉴스 크롤링 중 오류가 발생했습니다.")

#         # HTML 파싱
#         soup = BeautifulSoup(response.text, "html.parser")

#         # 뉴스 기사 목록 선택
#         articles = soup.select("#dnsColl > div:nth-child(1) > ul > li")

#         if not articles:
#             raise HTTPException(status_code=404, detail="뉴스 기사를 찾을 수 없습니다.")

#         news_list = []

#         for i in range(3):
#             title = soup.select("dnsColl > div:nth-child(1) > ul > li:nth-child(" + (
#                 i+1) + ") > div.c-item-content > div.item-bundle-mid > div.item-title > strong > a")
#             content = soup.select("dnsColl > div:nth-child(1) > ul > li:nth-child(" + (
#                 i+1) + ") > div.c-item-content > div.item-bundle-mid > div.item-contents > p > a")
#             image = soup.select("news_img_"+i+" > a")
#             date = soup.select("dnsColl > div:nth-child(1) > ul > li:nth-child(" + (i+1) +
#                                ") > div.c-item-content > div.item-bundle-mid > div.item-contents > span > span")

#             # 결과에 추가
#             news_list.append({
#                 "title": title,
#                 "content": content,
#                 "image": image,
#                 "date": date,

#             })

#         return news_list

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# dnsColl > div:nth-child(1) > ul > li:nth-child(1) > div.c-item-content > div.item-bundle-mid > div.item-title > strong > a
# dnsColl > div:nth-child(1) > ul > li:nth-child(2) > div.c-item-content > div.item-bundle-mid > div.item-title > strong > a
# dnsColl > div:nth-child(1) > ul > li:nth-child(3) > div.c-item-content > div.item-bundle-mid > div.item-title > strong > a

# dnsColl > div:nth-child(1) > ul > li:nth-child(1) > div.c-item-content > div.item-bundle-mid > div.item-contents > p > a
# dnsColl > div:nth-child(1) > ul > li:nth-child(2) > div.c-item-content > div.item-bundle-mid > div.item-contents > p > a

# dnsColl > div:nth-child(1) > ul > li:nth-child(2) > div.c-item-content > div.item-bundle-mid > div.item-contents > span > span

# news_img_0 > a


import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/news")
async def get_news():
    """
    다음 뉴스에서 '청계벽산아파트' 관련 최신 뉴스 크롤링
    """
    try:
        # 다음 뉴스 검색 URL
        search_url = "https://search.daum.net/search?w=news&q=서울숲트리마제"
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


#
# news_img_0
