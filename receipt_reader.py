"""영수증 사진 읽기 (2단계)

영수증 사진을 AI(사진을 읽을 수 있는 무료 모델)에 보내서
가게 이름, 산 날짜, 식재료 목록(이름·수량·단위·가격)을 받아 온다.
사진은 어디에도 저장하지 않는다. (공개 저장소에 영수증 사진이 올라가지 않게)

반환 예:
    {"store": "OO마트", "date": "2026-10-20",
     "items": [{"name": "우유", "quantity": 1, "unit": "팩", "price": 2980}, ...]}
"""

import re
from datetime import date, timedelta

import ai_client
import fridge_store

PROMPT = (
    "이 사진은 한국 마트/편의점 영수증입니다. 영수증에서 아래 정보를 읽어 JSON 한 개로만 답하세요.\n"
    "- store: 가게 이름 (모르면 빈 글자)\n"
    "- date: 구매 날짜 YYYY-MM-DD (모르면 null)\n"
    "- items: 산 물건 목록. 각 물건은 name, quantity, unit, price\n"
    "  * 먹는 것(식재료·음료·간식·간편식)만 넣고, 봉투·세제·휴지 같은 생활용품과 할인·합계 줄은 빼세요.\n"
    "  * name은 브랜드·용량을 뺀 간단한 재료 이름으로 (예: '서울우유 1L' → '우유', '국산콩두부300g' → '두부').\n"
    "  * quantity는 산 개수(숫자), unit은 다음 중 하나: " + ", ".join(fridge_store.UNITS) + "\n"
    "    포장 상품은 개수로 세고(두부 1모, 만두 1봉지, 우유 2팩), 고기·생선처럼 무게로 파는 것만 g으로 적으세요.\n"
    "    (예: 우유 2팩 → quantity 2, unit '팩' / 돼지고기 600g → quantity 600, unit 'g')\n"
    "  * price는 그 줄의 결제 금액(원, 숫자). 할인이 붙어 있으면 할인 뒤 금액.\n"
    "사진이 영수증이 아니거나 읽을 수 없으면 items를 빈 목록으로 답하세요.\n"
    '예: {"store": "OO마트", "date": "2026-10-20", "items": [{"name": "우유", "quantity": 1, "unit": "팩", "price": 2980}]}'
)


# AI가 가끔 넣는 먹는 것이 아닌 줄 (봉투·할인·합계 등). 이름에 이 글자가 있으면 뺀다.
NOT_FOOD = ["봉투", "봉지값", "쇼핑백", "세제", "휴지", "물티슈", "할인", "합계", "포인트", "부가세", "과세", "카드"]

# 개수로 세는 게 자연스러운 종류 (이런 재료가 g/ml로 오면 포장 하나로 고친다)
WEIGHT_CATEGORIES = {"육류", "해산물"}


def read_receipt(image_bytes, mime="image/jpeg"):
    """영수증 사진을 읽어서 결과 dict를 돌려준다. 실패하면 None."""
    return ai_client.ask_json_with_image(PROMPT, image_bytes, mime, validate=check_answer)


def check_answer(data):
    """AI 답을 확인하고 쓸 수 있는 모양으로 다듬는다. 쓸 수 없으면 None (다음 모델로)."""
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return None
    items = []
    for row in data["items"]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name or any(word in name for word in NOT_FOOD):
            continue
        unit = row.get("unit") if row.get("unit") in fridge_store.UNITS else "개"
        items.append(
            {
                "name": name,
                "quantity": _number(row.get("quantity"), default=1) or 1,
                "unit": unit,
                "price": _number(row.get("price"), default=None),
            }
        )
    return {
        "store": str(data.get("store") or "").strip(),
        "date": _date_text(data.get("date")),
        "items": items,
    }


def _number(value, default):
    """'2,980원' 같은 글자도 숫자로 바꾼다. 못 바꾸면 default."""
    if isinstance(value, (int, float)):
        return float(value)
    found = re.search(r"\d+(\.\d+)?", str(value or "").replace(",", ""))
    return float(found.group()) if found else default


def _date_text(value):
    """'2026.10.20', '26-10-20' 같은 날짜를 'YYYY-MM-DD'로 바꾼다. 이상하면 None."""
    numbers = re.findall(r"\d+", str(value or ""))
    if len(numbers) < 3:
        return None
    year, month, day = (int(n) for n in numbers[:3])
    if year < 100:
        year += 2000
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


# 영수증 표에 유통기한을 미리 채울 때 쓰는 종류별 보통 기한(일). 없는 종류는 비워 둔다(기한 없음).
# 포장에 적힌 날짜가 정확하므로, 화면에서 꼭 확인해서 고치도록 안내한다.
KEEP_DAYS = {"채소": 7, "과일": 7, "육류": 3, "해산물": 2, "유제품·계란": 10, "밀키트·간편식": 3}


def guess_expiry(category, storage, bought=None):
    """종류별 보통 기한으로 유통기한을 짐작한다. 냉동 보관이거나 모르는 종류면 None."""
    if storage == "냉동" or category not in KEEP_DAYS:
        return None
    return (bought or date.today()) + timedelta(days=KEEP_DAYS[category])


def fix_unit(item, info):
    """포장 상품인데 '두부 300g'처럼 무게로 읽힌 줄을 '두부 1모'처럼 고친다.

    info: classifier가 아는 이 재료의 분류 (모르면 None → 그대로 둔다)
    """
    if not info or info.get("category") in WEIGHT_CATEGORIES:
        return item
    if item["unit"] in ("g", "ml") and info.get("unit") not in ("g", "kg", "ml", "L") and item["quantity"] >= 50:
        return {**item, "quantity": 1.0, "unit": info["unit"]}
    return item
