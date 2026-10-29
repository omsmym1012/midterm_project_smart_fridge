"""재료를 사고·쓰고·버린 기록과 '한 번에 살 적정량' 추천 (3단계 구매 적정량)

유통기한 안에 다 못 쓰고 버리는 일을 줄이려고, 재료마다
    하루에 쓰는 양 × 보통 유통기한(일) = 한 번에 사기 알맞은 양
을 계산해서 장바구니에 넣을 때 추천한다.
최근 구매 중 버린 일이 2번 이상일 때만 추천한다. (가끔 한 번 버린 건 넘어간다)

[데이터 구조] data/usage_log.json (.gitignore의 data/*.json이라 커밋되지 않음)
    {"events": [
        {"kind": "buy", "name": "계란", "unit": "개", "quantity": 30, "date": "2026-10-01", "expiry": "2026-10-21"},
        {"kind": "use", "name": "계란", "unit": "개", "quantity": 2, "date": "2026-10-03"},
        {"kind": "discard", "name": "계란", "unit": "개", "quantity": 10, "date": "2026-10-22"}
    ]}
- 기록은 fridge_store가 재료를 넣고(buy)·쓰고(use)·버릴(discard) 때 남긴다.
- 잘못 넣은 재료를 지우거나 고치는 것은 기록하지 않는다.
"""

import json
import os
from datetime import date
from pathlib import Path

LOG_FILE = Path(__file__).parent / "data" / "usage_log.json"

RECENT_BUYS = 3      # 최근 몇 번의 구매를 볼지
MIN_DISCARDS = 2     # 이 중 몇 번 이상 버렸으면 추천할지


def load():
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, encoding="utf-8") as f:
            return json.load(f).get("events", [])
    except (json.JSONDecodeError, OSError):
        return []


def save(events):
    """임시 파일에 쓴 뒤 바꿔치기 (저장 도중 꺼져도 파일이 망가지지 않게)"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = LOG_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump({"events": events}, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, LOG_FILE)


def log(kind, name, unit, quantity, expiry=None, when=None):
    """기록 한 줄을 더한다. kind: "buy" / "use" / "discard", expiry: "YYYY-MM-DD" 또는 None"""
    if not quantity or quantity <= 0:
        return
    event = {"kind": kind, "name": name, "unit": unit, "quantity": quantity,
             "date": (when or date.today()).isoformat()}
    if kind == "buy":
        event["expiry"] = expiry
    events = load()
    events.append(event)
    save(events)


def _same(name):
    """이름 비교용: 띄어쓰기를 지우고 소문자로 (fridge_store.normalize_name과 같은 규칙)"""
    return "".join(name.split()).lower()


def _nice(value):
    """보여 줄 숫자: 1.0 → "1", 1.5 → "1.5" """
    return f"{value:g}"


def advice(name, unit, events=None, today=None):
    """이 재료를 한 번에 얼마나 사면 알맞은지. 추천할 게 없으면 None.

    반환: {"quantity": 추천 수량, "text": 이유 한 줄}
    """
    today = today or date.today()
    events = load() if events is None else events
    mine = [e for e in events if _same(e["name"]) == _same(name) and e["unit"] == unit]
    buys = sorted((e for e in mine if e["kind"] == "buy"), key=lambda e: e["date"])[-RECENT_BUYS:]
    if len(buys) < MIN_DISCARDS:
        return None

    # 구매마다 그다음 구매 날까지(마지막은 오늘까지) 버린 양을 센다.
    # 새로 사는 날 버린 것은 그 전에 산 것이라 앞 구매로 센다.
    ends = [b["date"] for b in buys[1:]] + ["9999-12-31"]
    discards = [e for e in mine if e["kind"] == "discard"]
    wasted = [sum(d["quantity"] for d in discards if b["date"] < d["date"] <= end) for b, end in zip(buys, ends)]
    wasted_times = sum(1 for w in wasted if w > 0)
    if wasted_times < MIN_DISCARDS:
        return None

    # 하루에 쓰는 양: 최근 구매 기간 동안 쓴 양 ÷ 날 수
    start = date.fromisoformat(buys[0]["date"])
    days = max((today - start).days, 1)
    used = sum(e["quantity"] for e in mine if e["kind"] == "use" and e["date"] >= buys[0]["date"])
    per_day = used / days

    # 보통 유통기한: 산 날부터 기한까지 며칠이었는지의 평균 (기한 없는 재료는 추천하지 않음)
    shelf = [(date.fromisoformat(b["expiry"]) - date.fromisoformat(b["date"])).days for b in buys if b.get("expiry")]
    if not shelf or per_day <= 0:
        return None
    shelf_days = round(sum(shelf) / len(shelf))

    quantity = max(1, round(per_day * shelf_days))
    usual = round(sum(b["quantity"] for b in buys) / len(buys))
    if quantity >= usual:
        return None  # 지금 사는 양이 이미 알맞다.
    avg_wasted = sum(wasted) / wasted_times
    text = (f"최근 {len(buys)}번 중 {wasted_times}번 버렸어요(평균 {_nice(round(avg_wasted, 1))}{unit}). "
            f"하루 {_nice(round(per_day, 1))}{unit}씩 쓰고 기한이 보통 {shelf_days}일이라 "
            f"{_nice(quantity)}{unit} 정도가 알맞아요.")
    return {"quantity": quantity, "text": text}


if __name__ == "__main__":
    # 자체 확인: 계란 30알을 20일마다(기한 20일) 3번 사서, 하루 1알 쓰고 매번 10알 버림 → 20알 추천
    from datetime import timedelta

    day0 = date(2026, 1, 1)
    sample = []
    for i in range(3):
        bought = day0 + timedelta(days=20 * i)
        sample.append({"kind": "buy", "name": "계란", "unit": "개", "quantity": 30,
                       "date": bought.isoformat(), "expiry": (bought + timedelta(days=20)).isoformat()})
        for d in range(20):
            sample.append({"kind": "use", "name": "계란", "unit": "개", "quantity": 1,
                           "date": (bought + timedelta(days=d)).isoformat()})
        sample.append({"kind": "discard", "name": "계란", "unit": "개", "quantity": 10,
                       "date": (bought + timedelta(days=20)).isoformat()})
    result = advice("계란", "개", sample, today=day0 + timedelta(days=60))
    assert result and result["quantity"] == 20, result
    assert advice("계란", "판", sample) is None          # 단위가 다르면 따로
    assert advice("계란", "개", sample[:22]) is None      # 한 번만 버렸으면 추천 안 함
    print("ok:", result["text"])
