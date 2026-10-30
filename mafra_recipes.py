"""농식품정보원(data.mafra.go.kr) 레시피 537개를 받아 recipes_mafra.json으로 저장한다.

식품안전나라 레시피에는 그냥 '된장찌개'·'김치찌개' 같은 기본 집밥 요리가 없어서 같이 쓴다.
이 API는 등록한 IP에서만 열리므로 배포 서버에서는 부를 수 없다.
그래서 내 컴퓨터에서 한 번 받아 파일로 저장해 두고, 앱(recipe_store.py)은 그 파일만 읽는다.

실행 (가상환경에서, .env에 MAFRA_API_KEY 필요): python mafra_recipes.py
"""

import json
from pathlib import Path

import requests

from ai_client import get_secret

OUT_FILE = Path(__file__).parent / "recipes_mafra.json"
API_URL = "http://211.237.50.150:7080/openapi/{key}/json/{grid}/{start}/{end}"
# 기본정보(이름·종류) / 재료 / 조리 과정이 서로 다른 표에 나뉘어 있고, RECIPE_ID로 이어 붙인다.
GRID_BASE, GRID_PARTS, GRID_STEPS = (
    "Grid_20150827000000000226_1", "Grid_20150827000000000227_1", "Grid_20150827000000000228_1"
)
PAGE_SIZE = 1000
SKIP_KINDS = {"양념장"}  # 간장·된장 담그기 같은 장 만들기는 요리 목록에서 뺀다.


def fetch(key, grid):
    """표 하나의 줄을 모두 받는다."""
    rows, start = [], 1
    while True:
        url = API_URL.format(key=key, grid=grid, start=start, end=start + PAGE_SIZE - 1)
        body = requests.get(url, timeout=30).json()[grid]
        if body["result"]["code"] != "INFO-000":
            raise RuntimeError(body["result"]["message"])
        rows += body["row"]
        start += PAGE_SIZE
        if start > body["totalCnt"]:
            return rows


def convert(base, parts, steps):
    """세 표를 recipe_store의 레시피 모양({id, name, kind, ...})으로 합친다."""
    parts_by, steps_by = {}, {}
    for row in sorted(parts, key=lambda r: r["IRDNT_SN"]):
        parts_by.setdefault(row["RECIPE_ID"], []).append(row)
    for row in sorted(steps, key=lambda r: r["COOKING_NO"]):
        steps_by.setdefault(row["RECIPE_ID"], []).append(row["COOKING_DC"].strip())
    recipes = []
    for row in base:
        rid = row["RECIPE_ID"]
        items = parts_by.get(rid, [])
        names = list(dict.fromkeys(p["IRDNT_NM"].strip() for p in items if p["IRDNT_NM"].strip()))
        if not names or not steps_by.get(rid) or row["TY_NM"] in SKIP_KINDS:
            continue
        recipes.append({
            "id": f"m{rid}",  # 식품안전나라 레시피 번호와 겹치지 않게
            "name": row["RECIPE_NM_KO"].strip(),
            "kind": row["TY_NM"],  # 밥, 찌개, 구이 등
            "way": "",
            "kcal": row["CALORIE"].lower().replace("kcal", "").strip(),
            "image": "",
            "parts": f"[{row['QNT']}] " + ", ".join(f"{p['IRDNT_NM']} {p['IRDNT_CPCTY']}".strip() for p in items),
            "ingredients": names,
            "steps": [f"{i}. {text}" for i, text in enumerate(steps_by[rid], 1) if text],
            "tip": row["SUMRY"].strip(),
        })
    return recipes


if __name__ == "__main__":
    key = get_secret("MAFRA_API_KEY")
    if not key:
        raise SystemExit(".env에 MAFRA_API_KEY가 없어요.")
    recipes = convert(fetch(key, GRID_BASE), fetch(key, GRID_PARTS), fetch(key, GRID_STEPS))
    OUT_FILE.write_text(json.dumps(recipes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(recipes)}개 저장: {OUT_FILE.name}")
