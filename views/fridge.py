"""🧊 냉장고 · 🛒 장보기 한 화면

- 맨 위: 유통기한 요약 문장 + [+ 재료 추가] [사용 (고른 개수)] (높이 고정 머리 영역)
- 가운데: 냉장고 칸 그림 (fridge_board.py)
  - 재료 카드를 끌어서 칸을 옮기고,
  - 누르면 고르기/풀기. 다 고른 뒤 [사용]을 누르면 재료마다 사용(양)·소진·폐기를 한 번에 처리한다.
- 냉장고 그림 위에 장보기 "문"(shopping_panel.py)을 겹쳐 두고, 문을 열고 닫아서 냉장고/장보기를 오간다.

app.py의 사이드바 메뉴에서 "냉장고"를 고르면 이 파일이 실행된다. 
"""

from datetime import date

import streamlit as st

import classifier
import fridge_store as store
import shopping_store as shop
import receipt_panel
import shopping_panel
import ui
from fridge_board import FRIDGE_HEIGHT, FRIDGE_HEIGHT_MOBILE, TRAY_GAP, TRAY_WIDTH, fridge_board
from fridge_board import recommend as board_recommend

MOBILE = ui.is_mobile()  # 휴대폰 화면이면 버튼·냉장고 그림 배치를 바꾼다.

# ---------------------------------------------------------------
# 냉장고 · 장보기 한 화면
# 냉장고 그림 위에 같은 크기의 "문"(장보기)을 겹쳐 두고, 문을 열고 닫아서 두 화면을 오간다.
# 페이지를 바꾸지 않고 문 모양(CSS)만 바꾸므로 열리고 닫히는 움직임이 부드럽다.
# 바꾸는 방법: 제목 옆 [냉장고 | 장보기] 버튼, 손잡이 누르기, 휴대폰 아래 메뉴의 '장보기'
# ---------------------------------------------------------------
VIEW_FRIDGE, VIEW_DOOR = "fridge", "door"
st.session_state.setdefault("home_view", VIEW_FRIDGE)
# 주소 끝 ?show=fridge|door 에 지금 보는 쪽을 늘 적어 둔다. → 새로고침해도 같은 화면
# 주소 값이 마지막으로 적은 값과 다르면(새로고침, 휴대폰 아래 메뉴 누름) 주소를 따른다.
show = st.query_params.get("show")
if show in (VIEW_FRIDGE, VIEW_DOOR) and show != st.session_state.get("shown_view"):
    st.session_state.home_view = show
st.query_params["show"] = st.session_state.shown_view = st.session_state.home_view
DOOR_CLOSED = st.session_state.home_view == VIEW_DOOR


def on_view_change():
    """제목 옆 버튼을 누르면 문을 열거나 닫는다. (이미 고른 쪽을 다시 누르면 그대로)"""
    picked = st.session_state.get("home_view_ctl")
    if picked:
        st.session_state.home_view = picked


# 제목 줄: 왼쪽 제목, 오른쪽 [🧊 냉장고 | 🛒 장보기] 전환 버튼
cart_count = shop.unchecked_count(shop.load())
# (휴대폰은 화면 아래 메뉴에 냉장고/장보기가 따로 있어서 제목만 둔다)
if MOBILE:
    st.title("🛒 장보기" if DOOR_CLOSED else "🧊 냉장고")
else:
    col_title, col_view = st.columns([1.2, 1], vertical_alignment="bottom")
    col_title.title("🛒 장보기" if DOOR_CLOSED else "🧊 냉장고")
    st.session_state.home_view_ctl = st.session_state.home_view  # 손잡이·메뉴로 바뀐 것도 버튼에 반영
    col_view.segmented_control(
        "보기", [VIEW_FRIDGE, VIEW_DOOR], key="home_view_ctl", on_change=on_view_change,
        format_func=lambda v: "🧊 냉장고" if v == VIEW_FRIDGE else f"🛒 장보기{f' {cart_count}' if cart_count else ''}",
        label_visibility="collapsed", width="stretch",
    )

# 화면이 다시 그려질 때마다 파일에서 최신 목록을 읽어 온다.
items = store.load_items()

# 분류 기능이 생기기 전에 넣은 재료가 있으면 한 번만 분류해 둔다.
for old_item in store.unclassified_items(items):
    with st.spinner(f"'{old_item['name']}' 분류 중..."):
        store.set_classification(items, old_item["id"], classifier.classify(old_item["name"]))

state = st.session_state

# ---------------------------------------------------------------
# 화면 상태 관리
# Streamlit은 버튼을 누를 때마다 코드를 다시 실행한다.
# 그래서 고른 재료와 열려 있는 팝업을 st.session_state(새로 실행돼도 유지되는 저장 공간)에 기억해 두고,
# 화면을 그릴 때마다 팝업을 다시 연다. 팝업의 ✕를 누르거나 작업이 끝나면 지워서 닫는다.
# ---------------------------------------------------------------
state.setdefault("add_open", False)     # 재료 추가 팝업이 열려 있는지
state.setdefault("multi_selected", [])  # 칸 그림에서 고른 재료 id들
state.setdefault("multi_open", False)   # 고른 재료 사용 팝업이 열려 있는지
state.setdefault("single_id", None)     # 우클릭(휴대폰은 길게 누르기)으로 하나만 사용하는 재료 id
state.setdefault("bulk_rebuy", None)    # 사용·소진·폐기로 없어진 재료들 (장바구니에 담을지 한 번에 묻기)

# 새로고침해도 열려 있던 팝업이 다시 뜨도록 주소 끝 ?popup=add|use|put (고른 재료는 &pick=id,id)에 적어 둔다.
# 새로고침하면 화면 기억이 비므로, 처음 실행할 때 한 번만 주소를 읽는다.
# 팝업 안에 적던 내용은 사용자별 저장소에 임시 저장해 두었다가 다시 채운다. (ui.save_draft / restore_draft)
POPUP_FLAGS = {"add": "add_open", "use": "multi_open", "put": "put_ask", "receipt": "receipt_open"}
if "popup_restored" not in state:
    state.popup_restored = True
    if st.query_params.get("pick"):
        state.multi_selected = st.query_params["pick"].split(",")
    if st.query_params.get("popup") in POPUP_FLAGS:
        state[POPUP_FLAGS[st.query_params["popup"]]] = True
    ui.restore_draft()
    if state.get("receipt_open") and state.get("receipt_draft"):
        state.receipt_rows = state.receipt_draft  # 영수증 표는 고친 내용까지 그대로


def close_dialogs():
    """팝업을 닫는다. (팝업 ✕를 눌렀을 때도 실행)"""
    state.add_open = False
    state.multi_open = False
    state.single_id = None
    state.receipt_open = False


# ---------------------------------------------------------------
# 유통기한 배지
# 상태마다 색과 아이콘을 정해 두고, Streamlit의 배지 문법 :색-badge[글자]로 표시한다.
# ---------------------------------------------------------------
STATUS_STYLE = {
    store.STATUS_EXPIRED: ("red", "🔴", "기한 지남"),
    store.STATUS_SOON: ("orange", "🟠", f"{store.SOON_DAYS}일 이내"),
    store.STATUS_OK: ("green", "🟢", "여유"),
    store.STATUS_NO_EXPIRY: ("gray", "⚪", "기한 없음"),
}


def expiry_badge(expiry_str):
    """유통기한 상태에 맞는 색깔 D-day 배지 (마크다운 글자)"""
    color, icon, _ = STATUS_STYLE[store.expiry_status(expiry_str)]
    return f":{color}-badge[{icon} {store.d_day_label(expiry_str)}]"


WEEK_DAYS = 7  # 맨 위 요약의 "7일 이내" (3일 이내와 겹치지 않게 4~7일 남은 재료)


def summary_badges():
    """맨 위 한 줄 요약 문장: 기한 지난 재료(빨간 굵은 글씨) / 3일 안 / 일주일 안에 먹을 재료 개수

    여유·기한 없음 재료는 세지 않는다. 모두 0이면 급한 재료가 없다고 알려 준다.
    (ui.py의 .ft-summary 스타일, markdown(unsafe_allow_html=True)로 보여 준다)
    """
    groups = store.expiry_summary(items)
    expired = len(groups[store.STATUS_EXPIRED])
    soon = len(groups[store.STATUS_SOON])
    week = len([
        item for item in groups[store.STATUS_OK]
        if store.days_left(store.earliest_batch(item)["expiry"]) <= WEEK_DAYS
    ])
    parts = []
    if expired:
        parts.append(f"<b>기한 지난 재료 {expired}개</b>")
    if soon:
        parts.append(f"{store.SOON_DAYS}일 안에 먹을 재료 {soon}개")
    if week:
        parts.append(f"일주일 안에 먹을 재료 {week}개")
    text = ", ".join(parts) if parts else "급하게 먹어야 할 재료가 없어요."
    return f'<p class="ft-summary">{text}</p>'


# ---------------------------------------------------------------
# 1) 재료 추가 (팝업)
# 이름을 입력하고 Enter를 누르거나 다른 칸을 누르면(on_change) 바로 분류해서
# 종류·보관 방법·추천 단위를 채워 준다. 사용자는 "추가"를 누르기 전에 바꿀 수 있다.
# 여러 재료를 연달아 넣을 수 있게 추가한 뒤에도 팝업은 열어 둔다. (닫으면 칸 그림이 새로 그려짐)
#
# 입력칸 값은 key 이름으로 st.session_state에 들어 있다. (예: st.session_state.add_name)
# 콜백 함수에서 이 값을 바꾸면 화면의 입력칸 값도 바뀐다.
# ---------------------------------------------------------------
ADD_DEFAULTS = {
    "add_name": "",
    "add_expiry": date.today(),
    "add_no_expiry": False,
    "add_quantity": 1.0,
    "add_category": classifier.DEFAULT_CATEGORY,
    "add_storage": classifier.DEFAULT_STORAGE,
    "add_unit": classifier.DEFAULT_UNIT,
    "add_tip": "",
    "add_suggested": None,  # 자동 분류가 추천한 값 (사용자가 바꿨는지 비교용)
    "add_existing": None,   # 같은 이름이 이미 있으면 {"name": 이름, "units": [단위들]}
    "add_confirm": None,    # 단위가 달라서 확인을 기다리는 중이면 안내 문구
}
for key, value in ADD_DEFAULTS.items():
    state.setdefault(key, value)


def reset_add_inputs():
    """추가가 끝나면 입력칸을 처음 상태로 되돌린다."""
    for key, value in ADD_DEFAULTS.items():
        state[key] = value


def on_name_change():
    """이름 칸이 바뀌었을 때: 분류하고 추천 값을 입력칸에 채운다."""
    name = state.add_name.strip()
    state.add_confirm = None  # 이름이 바뀌면 이전 확인 창은 닫는다.
    if not name:
        reset_add_inputs()
        return

    same_name = store.find_all_by_name(store.load_items(), name)
    if same_name:
        # 이미 있는 재료면 기존 기록(첫 번째 줄)의 분류·단위를 그대로 채운다. 바꾸는 건 자유.
        first = same_name[0]
        values = {
            "category": first["category"], "storage": first["storage"],
            "unit": first["unit"], "tip": first.get("tip", ""),
        }
        state.add_existing = {"name": first["name"], "units": [item["unit"] for item in same_name]}
        state.add_suggested = None
    else:
        with st.spinner(f"'{name}' 분류 중..."):
            values = classifier.classify(name)
        state.add_existing = None
        state.add_suggested = values

    state.add_category = values["category"]
    state.add_storage = values["storage"]
    state.add_unit = values["unit"]
    state.add_tip = values["tip"]


def on_unit_change():
    """단위를 바꾸면 이전 확인 창은 닫는다. (다시 '추가'를 누를 때 새로 확인)"""
    state.add_confirm = None


def with_gwa(word):
    """이름 뒤에 '과' 또는 '와'를 붙인다. 마지막 글자에 받침이 있으면 '과', 없으면 '와'.

    예: '우유' → "'우유'와", '연근' → "'연근'과"
    한글 글자는 (코드값 - 0xAC00) % 28 이 0이 아니면 받침이 있다.
    """
    last = word[-1]
    if "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0:
        return f"'{word}'과"
    return f"'{word}'와"


def cancel_confirm():
    state.add_confirm = None


def on_add_click(confirmed=False):
    """'추가' 버튼: 입력한 값으로 재료를 추가한다. 결과는 팝업 안(add_msg)에 보여 준다.

    confirmed: 단위가 달라 따로 추가된다는 확인 창에서 '이대로 추가'를 눌렀으면 True
    """
    name = state.add_name.strip()
    if not name:
        state.add_msg = (False, "재료 이름을 입력해 주세요.")
        return

    # 이름을 입력하고 Enter 없이 바로 '추가'를 누른 경우에도 분류가 되도록 한 번 더 확인한다.
    if state.add_suggested is None and state.add_existing is None:
        on_name_change()

    # 같은 이름이 있는데 고른 단위가 기존 단위와 다르면, 바로 추가하지 않고 먼저 확인을 받는다.
    existing = state.add_existing
    if existing and state.add_unit not in existing["units"] and not confirmed:
        state.add_confirm = f"냉장고에 있는 {with_gwa(existing['name'])} 단위가 달라요. 이대로 추가할까요?"
        return

    classification = {"category": state.add_category, "storage": state.add_storage, "tip": state.add_tip}
    expiry = None if state.add_no_expiry else state.add_expiry
    ok, message = store.add_item(
        store.load_items(), name, expiry, state.add_quantity, state.add_unit, classification,
        allow_new_unit=confirmed,
    )

    if ok:
        suggested = state.add_suggested
        # 추천과 다르게 고쳤으면 기억해 두고, 다음에 같은 이름을 넣을 때 그 값을 추천한다.
        if suggested and (state.add_category, state.add_storage, state.add_unit) != (
            suggested["category"], suggested["storage"], suggested["unit"]
        ):
            classifier.remember(name, state.add_category, state.add_storage, state.add_unit, state.add_tip)
        elif suggested and suggested["source"] == "default":
            message += " (자동 분류에 실패해서 기본값으로 넣었어요. 재료를 눌러 '수정'에서 바꿀 수 있어요.)"
        reset_add_inputs()
    state.add_msg = (ok, message)


@st.dialog("재료 추가", on_dismiss=close_dialogs)
def add_dialog():
    """[+ 재료 추가] 팝업. 닫으면 페이지를 다시 그려 칸 그림에 새 재료가 나온다."""
    if "add_msg" in state:
        ok, message = state.pop("add_msg")
        (st.success if ok else st.warning)(message)

    st.text_input(
        "이름", key="add_name", on_change=on_name_change,
        placeholder="예: 우유 (입력 후 Enter를 누르면 자동 분류)",
    )
    if state.add_suggested and state.add_suggested["source"] == "default":
        st.caption("⚠️ 자동 분류에 실패했어요. 종류와 보관 방법을 직접 골라 주세요.")

    col_cat, col_storage = st.columns(2)
    col_cat.selectbox("종류", classifier.CATEGORIES, key="add_category")
    col_storage.selectbox("보관 방법", classifier.STORAGES, key="add_storage")
    if state.add_tip:
        st.caption(f"💡 {state.add_tip}")

    col_date, col_none = st.columns([2, 1])
    with col_none:
        st.write("")  # 체크박스를 날짜 칸 높이에 맞추기 위한 빈 줄
        no_expiry = st.checkbox(
            "기한 없음", key="add_no_expiry", help="소금·간장처럼 기한이 없거나 모를 때 체크하세요."
        )
    with col_date:
        st.date_input("유통기한", key="add_expiry", disabled=no_expiry)

    # 단위는 그 재료에 흔히 쓰는 것만 고를 수 있다. (종류별 목록 + 추천 단위 + 냉장고에 있던 단위)
    suggested_unit = (state.add_suggested or {}).get("unit")
    existing_units = (state.add_existing or {}).get("units", [])
    unit_options = classifier.common_units(state.add_category, *existing_units, suggested_unit)
    if state.add_unit not in unit_options:
        state.add_unit = unit_options[0]
    col_qty, col_unit = st.columns([2, 1])
    col_qty.number_input("수량", min_value=0.1, step=1.0, format="%g", key="add_quantity")
    col_unit.selectbox("단위", unit_options, key="add_unit", on_change=on_unit_change)

    col_add, col_receipt = st.columns([1, 2], vertical_alignment="center")
    col_add.button("추가", type="primary", on_click=on_add_click, width="stretch")
    # 장 본 재료가 많으면 영수증으로 한 번에 넣는 게 편하다. (이 팝업을 닫고 영수증 팝업을 연다)
    if col_receipt.button("🧾 영수증으로 한 번에 추가", type="tertiary"):
        go_receipt()
        st.rerun()

    # 단위가 달라 따로 추가되는 경우의 확인 창
    if state.add_confirm:
        st.warning(state.add_confirm)
        st.caption("단위가 다르면 따로 추가돼요.")
        col_ok, col_cancel = st.columns(2)
        col_ok.button("이대로 추가", on_click=on_add_click, kwargs={"confirmed": True})
        col_cancel.button("취소", key="cancel_add_confirm", on_click=cancel_confirm)
    ui.save_draft()


# ---------------------------------------------------------------
# 4) 고른 재료 사용 (칸 그림에서 재료를 눌러 고르고 [사용])
#   칸 그림에서 재료를 눌러 고르기(다시 누르면 풀림) → 위쪽 [사용 (고른 개수)]
#   → 재료마다 [사용(양 입력) / 소진 / 폐기(기한 지난 재료만)]를 고르는 팝업 → [적용하기]
#   → 다 쓰거나 버려서 없어진 재료가 있으면 장바구니에 담을지 한 번에 묻는 팝업
# ---------------------------------------------------------------
def clear_keys(prefix):
    """이전 팝업에서 입력한 값이 남지 않게, 이름이 prefix로 시작하는 입력칸 값을 지운다."""
    for key in [k for k in state.keys() if str(k).startswith(prefix)]:
        del state[key]


def clear_selection():
    """고른 재료를 모두 풀어 준다."""
    state.multi_selected = []


def discard_selected():
    """[폐기]: 고른 재료(모두 기한 지난 재료)의 기한 지난 묶음을 팝업 없이 바로 버린다."""
    all_items = store.load_items()
    done, gone = [], []
    for item in store.fridge_items_sorted(all_items):
        expired = store.expired_batches(item)
        if item["id"] not in state.multi_selected or not expired:
            continue
        store.discard_batches(all_items, item["id"], [b["id"] for b in expired])
        done.append(item["name"])
        if item["status"] == store.STATUS_USED:
            gone.append({"item_id": item["id"], "name": item["name"], "unit": item["unit"],
                         "source": shop.SOURCE_DISCARDED})
    clear_selection()
    message = f"폐기했어요: {', '.join(done)}."
    if gone:
        # 없어진 재료는 장바구니에 담을지 한 번에 묻는다. (사용 팝업과 같은 방식)
        clear_keys("bulk_")
        state.bulk_rebuy = {"items": gone, "message": message}
    else:
        state.flash = (True, message)


def open_use_dialog():
    """[사용]: 고른 재료들을 한 번에 다루는 팝업을 연다."""
    close_dialogs()
    clear_keys("multi_act_")  # 이전 팝업에서 고른 처리 방법·양은 지운다. (고른 재료 목록은 그대로)
    clear_keys("multi_amt_")
    state.multi_open = True


def on_toggle():
    """칸 그림에서 재료를 누르면 고른 목록에 넣거나 뺀다."""
    item_id = (state.get(BOARD_KEY) or {}).get("toggle")
    if not item_id:
        return
    if item_id in state.multi_selected:
        state.multi_selected = [i for i in state.multi_selected if i != item_id]
    else:
        state.multi_selected = state.multi_selected + [item_id]


ACT_USE, ACT_EMPTY, ACT_DISCARD = "사용", "소진", "폐기"


def on_detail():
    """재료 우클릭(휴대폰은 길게 누르기): 그 재료 하나만 사용하는 팝업을 연다. (고른 목록은 그대로)"""
    item_id = (state.get(BOARD_KEY) or {}).get("detail")
    if item_id:
        close_dialogs()
        clear_keys("multi_act_")
        clear_keys("multi_amt_")
        state.single_id = item_id


@st.dialog("고른 재료 사용", on_dismiss=close_dialogs)
def multi_dialog():
    use_body([i for i in store.fridge_items_sorted(items) if i["id"] in state.multi_selected], from_selection=True)


@st.dialog("재료 사용", on_dismiss=close_dialogs)
def single_dialog():
    use_body([i for i in store.fridge_items_sorted(items) if i["id"] == state.single_id], from_selection=False)


def use_body(chosen, from_selection):
    """재료마다 쓰는 양을 입력하거나 [소진]/[폐기]를 골라 한 번에 적용한다. (여러 개 / 하나 팝업 공통)

    - 사용: 쓰는 양만큼 줄인다. (0이면 그대로)
    - 소진: 쓰는 양 칸을 남은 양 전부로 채운다. (적용하면 다 쓴 것이 된다)
    - 폐기: 유통기한이 지난 묶음만 버린다. (기한 지난 묶음이 있는 재료에만 보인다)
    다 쓰거나 버려서 없어진 재료는 마지막에 장바구니에 담을지 한 번에 묻는다.
    """
    if not chosen:
        st.info("고른 재료가 없어요." if from_selection else "이미 다 쓰거나 버린 재료예요.")
        return
    plans = {}
    for item in chosen:
        total = store.total_quantity(item)
        first = store.earliest_batch(item)
        expired = store.expired_batches(item)
        with st.container(border=True):
            st.markdown(
                f"**{item['name']}** {expiry_badge(first['expiry'])} "
                f":gray[남은 양 {store.format_quantity(total, item['unit'])}]"
            )
            # 한 줄: [쓰는 양(짧은 칸)] 단위 [소진] [폐기]
            # [소진]은 쓰는 양을 남은 양 전부로 바꾼다. [폐기]를 고르면 쓰는 양 칸은 잠긴다. (다시 누르면 풀림)
            with st.container(horizontal=True, vertical_alignment="center", gap="small", wrap=MOBILE):  # 휴대폰은 좁으면 [소진][폐기]가 다음 줄로
                act_key = f"multi_act_{item['id']}"
                picked_act = state.get(act_key)
                amount = st.number_input(
                    f"{item['name']} 쓰는 양", min_value=0.0, max_value=float(total),
                    value=float(min(1.0, total)), step=1.0, format="%g", key=f"multi_amt_{item['id']}",
                    label_visibility="collapsed", width=130, disabled=bool(picked_act),  # 130px부터 [−][+]가 보인다
                )
                st.markdown(item["unit"], width="content")
                st.button(
                    ACT_EMPTY, key=f"multi_full_{item['id']}", disabled=bool(picked_act),
                    on_click=lambda key=f"multi_amt_{item['id']}", total=total: state.update({key: float(total)}),
                )
                act = (st.segmented_control(
                    f"{item['name']} 처리", [ACT_DISCARD], key=act_key, label_visibility="collapsed",
                ) if expired else None) or ACT_USE  # 폐기는 기한 지난 재료만
            if act == ACT_DISCARD:
                gone_qty = sum(b["quantity"] for b in expired)
                st.caption(f"기한 지난 {store.format_quantity(gone_qty, item['unit'])}을(를) 버려요.")
            if act != ACT_USE:
                amount = 0.0
            plans[item["id"]] = (item, act, amount, expired)
    ui.save_draft()

    if st.button("적용하기", type="primary", width="stretch"):
        done, gone = [], []
        for item, act, amount, expired in plans.values():
            if act == ACT_USE:
                if amount <= 0:
                    continue
                all_used = amount >= store.total_quantity(item)
                store.use_quantity(items, item["id"], amount)  # 남은 양을 다 쓰면 '다 씀'이 된다.
                done.append(f"{item['name']} 소진" if all_used else
                            f"{item['name']} {store.format_quantity(amount, item['unit'])} 사용")
                source = shop.SOURCE_USED
            else:
                store.discard_batches(items, item["id"], [b["id"] for b in expired])
                done.append(f"{item['name']} 폐기")
                source = shop.SOURCE_DISCARDED
            if item["status"] == store.STATUS_USED:
                gone.append({"item_id": item["id"], "name": item["name"], "unit": item["unit"], "source": source})
        if from_selection:
            clear_selection()  # 하나만 쓸 때는 다른 재료를 골라 둔 것은 그대로 둔다.
        close_dialogs()
        message = f"처리했어요: {', '.join(done)}." if done else "바뀐 재료가 없어요."
        if gone:
            # 없어진 재료가 있으면 장바구니에 담을지 한 번에 묻는다.
            clear_keys("bulk_")
            state.bulk_rebuy = {"items": gone, "message": message}
        else:
            state.flash = (bool(done), message)
        st.rerun()


def close_bulk_rebuy():
    """✕로 닫으면 묻지 않은 것으로 둔다. (장보기의 '다시 사기'에 그대로 남는다)"""
    state.bulk_rebuy = None


@st.dialog("🛒 장보기", on_dismiss=close_bulk_rebuy)
def bulk_rebuy_dialog():
    """사용·소진·폐기로 없어진 재료들을 장바구니에 담을지 한 번에 묻는다."""
    info = state.bulk_rebuy
    st.write(info["message"])
    st.markdown("**다 쓰거나 버린 재료를 장바구니에 담을까요?**")
    picks = []
    for gone in info["items"]:
        col_check, col_qty = st.columns([1.4, 1], vertical_alignment="center")
        if col_check.checkbox(gone["name"], value=True, key=f"bulk_chk_{gone['item_id']}"):
            quantity = col_qty.number_input(
                f"수량 ({gone['unit']})", min_value=0.1, value=1.0, step=1.0, format="%g",
                key=f"bulk_qty_{gone['item_id']}",
            )
            picks.append((gone, quantity))
    ui.save_draft()

    col_yes, col_no = st.columns(2)
    add = col_yes.button("추가", type="primary", width="stretch", disabled=not picks)
    skip = col_no.button("추가 안 함", width="stretch")
    if add or skip:
        data = shop.load()
        added, already = [], []
        if add:
            for gone, quantity in picks:
                ok, _ = shop.add_item(data, gone["name"], quantity, gone["unit"], gone.get("source", shop.SOURCE_USED))
                (added if ok else already).append(gone["name"])
        # 물어본 재료는 장보기의 '다시 사기'에 다시 나오지 않게 한다.
        shop.mark_handled(data, [f"used:{gone['item_id']}" for gone in info["items"]])
        message = info["message"]
        if added:
            message += f" 🛒 장바구니에 담았어요: {', '.join(added)}"
        if already:
            message += f" (이미 있음: {', '.join(already)})"
        state.bulk_rebuy = None
        state.flash = (True, message)
        st.rerun()


# ---------------------------------------------------------------
# 5) 맨 위: 상태별 개수 + [+ 재료 추가] [사용 (고른 개수)]
# ---------------------------------------------------------------
def go_receipt():
    """[🧾 영수증]: 다른 팝업을 닫고 영수증 등록 팝업을 연다."""
    close_dialogs()
    receipt_panel.open_receipt()


def open_add_dialog():
    close_dialogs()
    state.pop("add_msg", None)
    state.add_open = True


# 머리 영역(높이 고정): 요약 + [＋ 재료 추가] + [사용 (고른 개수)]
# 높이가 늘 같아서 아래 냉장고 그림이 장보기의 닫힌 문과 같은 자리에 온다.
alive = {i["id"] for i in store.fridge_items_sorted(items)}
state.multi_selected = [i for i in state.multi_selected if i in alive]  # 없어진 재료는 선택에서 뺀다.
# 봉투에서 추천 칸으로 자동으로 넣어 노란색으로 표시 중인 재료 (fridge.json의 "new" 표시라 새로고침해도 남는다)
new_ids = [i["id"] for i in store.fridge_items_sorted(items) if i.get("new") and i.get("zone") in store.ZONES]
picked = len(state.multi_selected)
use_label = f"사용 ({picked})" if picked else "사용"
# 고른 재료가 모두 기한 지난 재료면 [사용]을 반으로 줄이고 옆에 [폐기]를 둔다. (팝업 없이 바로 버리기)
all_expired = picked > 0 and all(
    store.expired_batches(i) for i in store.fridge_items_sorted(items) if i["id"] in state.multi_selected
)
head = ui.page_head(MOBILE)
if not DOOR_CLOSED:
    with head:
        if MOBILE:
            # 휴대폰: 요약 한 줄 아래에 버튼 3개를 가로로 (장보기 쪽 머리 영역과 같은 자리)
            st.markdown(summary_badges(), unsafe_allow_html=True)
            with st.container(key="row_buttons"):
                if all_expired:
                    col_add, col_receipt, col_use, col_discard = st.columns([1, 1.1, 0.75, 0.75])
                    col_discard.button("폐기", key="head_discard", width="stretch", on_click=discard_selected)
                    use_label = "사용"  # 반 칸이라 개수는 뺀다.
                else:
                    col_add, col_receipt, col_use = st.columns([1, 1.1, 1])
                col_add.button("＋ 추가", width="stretch", on_click=open_add_dialog)
                col_receipt.button("🧾 영수증", width="stretch", on_click=go_receipt)
                col_use.button(use_label, type="primary", width="stretch", on_click=open_use_dialog,
                               disabled=not picked)
        else:
            # PC: 왼쪽 요약·도움말(고른 게 있으면 [선택 해제]), 오른쪽 [＋ 재료 추가][🧾 영수증]과 그 아래 [사용]
            col_summary, col_buttons = st.columns([3.2, 2], vertical_alignment="center")
            col_summary.markdown(summary_badges(), unsafe_allow_html=True)
            if picked:
                col_summary.button(f"✕ 선택 해제 ({picked})", type="tertiary", on_click=clear_selection)
            else:
                col_summary.caption("재료를 눌러 고르고 [사용]을 누르세요. 우클릭하면 하나만 사용, 끌면 칸 이동.")
            col_add, col_receipt = col_buttons.columns(2, gap="small")
            col_add.button("＋ 재료 추가", width="stretch", on_click=open_add_dialog)
            col_receipt.button("🧾 영수증", width="stretch", on_click=go_receipt)
            col_use, col_discard = col_buttons.columns(2, gap="small") if all_expired else (col_buttons, None)
            col_use.button(use_label, type="primary", width="stretch", on_click=open_use_dialog,
                           disabled=not picked)
            if col_discard:
                col_discard.button(f"폐기 ({picked})", key="head_discard", width="stretch", on_click=discard_selected)

# 직전 작업의 결과 메시지 (자리를 차지하지 않는 알림)
ui.show_flash()


# ---------------------------------------------------------------
# 6) 냉장고 칸 그림
# 재료를 끌어서 놓으면 on_move, 누르면 on_toggle(고르기/풀기)이 페이지를 다시 그리기 전에 실행된다.
# ---------------------------------------------------------------
BOARD_KEY = "fridge_board"


def on_move():
    """재료를 놓으면 칸과 순서를 저장한다. (저장한 뒤에 그려야 원래 자리로 되돌아가 보이지 않는다)"""
    move = (state.get(BOARD_KEY) or {}).get("move")
    if move:
        all_items = store.load_items()
        item = next((i for i in all_items if i["id"] == move.get("item_id")), None)
        from_bag = item is not None and item.get("zone") not in store.ZONES
        moved = store.place_in_zone(all_items, move.get("item_id"), move.get("zone"), move.get("before"))
        if moved and from_bag:
            item["new"] = True  # 봉투에서 직접 꺼내 넣은 재료도 [완료]를 누를 때까지 노란색
            store.save_items(all_items)


def place_from_bag(only_zone=None):
    """봉투의 재료를 추천 칸에 넣고, 넣은 재료를 "새"로 표시해 둔다. only_zone이 있으면 그 칸이 추천인 재료만."""
    all_items = store.load_items()
    cache = classifier.load_cache()
    placed = []
    for item in store.fridge_items_sorted(all_items):
        zone = board_recommend(item, cache)
        if item.get("zone") not in store.ZONES and only_zone in (None, zone) \
                and store.set_zone(all_items, item["id"], zone):
            placed.append(item)
    for item in placed:
        item["new"] = True  # [완료]를 누를 때까지 노란색으로 표시
    if placed:
        store.save_items(all_items)
        state.flash = (True, f"추천 칸에 넣었어요: {', '.join(item['name'] for item in placed)}")
    elif only_zone:
        state.flash = (False, "새 재료 중에 이 칸이 추천 칸인 재료가 없어요.")


def on_autoplace():
    """봉투의 [추천 칸에 모두 넣기]"""
    place_from_bag()


def on_fill():
    """칸 이름 더블클릭: 그 칸이 추천 칸인 봉투 재료만 넣는다."""
    fill = (state.get(BOARD_KEY) or {}).get("fill") or {}
    if fill.get("zone") in store.ZONES:
        place_from_bag(fill["zone"])


def on_done():
    """[완료]: "새" 표시를 지워서 다른 재료와 똑같이 보이게 한다."""
    all_items = store.load_items()
    for item in all_items:
        item.pop("new", None)
    store.save_items(all_items)


def on_undo():
    """[취소]: 노란색으로 표시된(봉투에서 넣은) 재료를 다시 새 재료 봉투로 돌려놓는다."""
    all_items = store.load_items()
    undone = 0
    for item in all_items:
        if item.pop("new", None):
            item["zone"] = None
            undone += 1
    store.save_items(all_items)
    if undone:
        state.flash = (True, f"넣기를 취소했어요. 재료 {undone}개가 새 재료 봉투로 돌아갔어요.")


def on_close_door():
    """냉장고 그림의 손잡이를 누르면 문을 닫는다. → 장보기"""
    state.home_view = VIEW_DOOR


# 문 모양(열림/닫힘). 바뀔 때마다 CSS transition으로 부드럽게 돈다.
st.html(shopping_panel.door_css(
    DOOR_CLOSED, FRIDGE_HEIGHT_MOBILE if MOBILE else FRIDGE_HEIGHT, MOBILE, state.get("page_changed", False),
    right=0 if MOBILE else TRAY_WIDTH + TRAY_GAP,  # PC: 옆의 새 재료 봉투는 가리지 않는다.
))
with st.container(key="fridge_stage"):
    fridge_board(
        items, key=BOARD_KEY, on_move=on_move, on_toggle=on_toggle, selected=state.multi_selected,
        on_close=on_close_door,
        # 다른 페이지에서 냉장고(문 열린 상태)로 들어왔을 때만 문 열림 효과
        animate=state.get("page_changed", False) and not DOOR_CLOSED, mobile=MOBILE,
        hide_outside=DOOR_CLOSED,  # 문이 닫히면(장보기) 냉장고 밖(실온)은 안 보이게
        new_ids=new_ids, on_autoplace=on_autoplace, on_done=on_done, on_undo=on_undo, on_fill=on_fill, on_detail=on_detail,
    )
    door = st.container(key="fridge_door", gap="small")
shopping_panel.render(head, door, MOBILE, show_head=DOOR_CLOSED)

# 지금 열린 팝업과 고른 재료를 주소에 적는다. (없으면 지운다)
for param, value in (
    ("popup", next((name for name, flag in POPUP_FLAGS.items() if state.get(flag)), None)),
    ("pick", ",".join(state.multi_selected)),
):
    if value:
        st.query_params[param] = value
    else:
        st.query_params.pop(param, None)
ui.save_draft()  # 팝업이 닫혔으면 임시 저장도 비운다.

# 열려 있어야 하는 팝업을 연다. (한 번에 하나만)
if state.bulk_rebuy:
    bulk_rebuy_dialog()
elif state.multi_open:
    multi_dialog()
elif state.single_id:
    single_dialog()
elif state.add_open:
    add_dialog()
elif state.get("receipt_open"):
    receipt_panel.receipt_dialog()
