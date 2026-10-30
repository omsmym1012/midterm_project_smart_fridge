"""농촌진흥청 메뉴젠(식단관리) 요리 3천여 개를 받아 recipes_menugen.json으로 저장한다.

짜장면·새우볶음밥처럼 다른 두 레시피 목록에 없는 흔한 요리가 많다. 다만 재료만 있고 조리 순서는 비어 있다.
공공누리 4유형(출처표시·상업적 이용 금지·변경 금지)이라 화면의 '재료 전체'(parts)는 받은 그대로 보여 준다.
(냉장고 재료와 비교하고 장바구니에 담을 때만 '양배추, 생것'의 앞부분 '양배추'를 쓴다)

한 번에 20개씩만 주고 하루 호출 횟수 제한이 있어서, 받은 페이지를 data/menugen_pages.json에 모아 두고
제한에 걸리면 다음에 이어서 받는다.

실행 (가상환경에서, .env에 DATA_GO_KR_KEY 필요): python menugen_recipes.py
"""

import json
import re
from pathlib import Path

import requests

from ai_client import get_secret

ROOT = Path(__file__).parent
OUT_FILE = ROOT / "recipes_menugen.json"
PAGES_FILE = ROOT / "data" / "menugen_pages.json"  # 받는 중인 페이지 (data/라 커밋되지 않음)
API_URL = "https://apis.data.go.kr/1390803/AgriFood/FdFoodCkryImage1/getKoreanFoodFdFoodCkryImageList1"
PAGE_SIZE = 20  # API가 허용하는 최대


def fetch_page(key, page):
    """page번째 20개. 반환: (요리 목록, 전체 개수). 실패하면 RuntimeError"""
    params = {"serviceKey": key, "service_Type": "json", "page_No": page, "Page_Size": PAGE_SIZE, "food_Name": ""}
    text = requests.get(API_URL, params=params, timeout=30).text
    body = json.loads(re.sub(r",\s*,", ",", text))["response"]  # 응답에 ", ,"가 섞여 오는 경우가 있다.
    if body.get("result_Code") != "200":
        raise RuntimeError(body.get("resultMsg") or body.get("result_Msg") or "알 수 없는 오류")
    return body["list"], int(body["total_Count"])


def convert(item):
    """메뉴젠 요리 하나를 recipe_store의 레시피 모양으로 바꾼다."""
    foods = [f for f in item.get("food_List") or [] if f.get("food_Nm") not in (None, "null")]
    return {
        "id": f"g{item['fd_Code']}",  # 다른 목록의 번호와 겹치지 않게
        "name": item["fd_Nm"].strip(),
        "kind": item["fd_Grupp_Nm"],
        "way": "",
        "kcal": "",
        "image": "",
        "parts": ", ".join(
            f"{f['food_Nm']} {float(f['food_Wgh']):g}g" if re.fullmatch(r"[\d.]+", str(f.get("food_Wgh"))) else f["food_Nm"]
            for f in foods
        ),
        # 냉장고 비교·장바구니에는 이름 앞부분만 ('양배추, 생것' → '양배추'). 받은 그대로의 이름은 parts에 있다.
        "ingredients": list(dict.fromkeys(f["food_Nm"].split(",")[0].strip() for f in foods)),
        "steps": [],  # 메뉴젠에는 조리 순서가 없다.
        "tip": "",
    }


if __name__ == "__main__":
    key = get_secret("DATA_GO_KR_KEY")
    if not key:
        raise SystemExit(".env에 DATA_GO_KR_KEY가 없어요.")
    pages = json.loads(PAGES_FILE.read_text(encoding="utf-8")) if PAGES_FILE.exists() else {}
    _, total = fetch_page(key, 1)
    last = -(-total // PAGE_SIZE)
    try:
        for page in range(1, last + 1):
            if str(page) not in pages:
                pages[str(page)] = fetch_page(key, page)[0]
                print(f"\r{page}/{last}", end="", flush=True)
    except (RuntimeError, requests.RequestException, ValueError, KeyError) as error:
        print(f"\n{len(pages)}/{last} 페이지에서 멈췄어요 ({error}). 다시 실행하면 이어서 받아요.")
        raise SystemExit(1)
    finally:
        PAGES_FILE.parent.mkdir(exist_ok=True)
        PAGES_FILE.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    items = [item for page in pages.values() for item in page]
    recipes = list({r["id"]: r for r in map(convert, items) if r["ingredients"]}.values())
    OUT_FILE.write_text(json.dumps(recipes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\n{len(recipes)}개 저장: {OUT_FILE.name}")
