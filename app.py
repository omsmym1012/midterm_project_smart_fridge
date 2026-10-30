"""스마트 냉장고 & 장보기 리스트 - Streamlit 앱 진입 파일.

실행: streamlit run app.py

이 파일은 사이드바 메뉴(휴대폰은 아래쪽 메뉴 막대)와 앱 전체 스타일만 담당하고,
실제 화면은 views/ 폴더의 페이지 파일이 그린다.
    views/fridge.py   🧊 냉장고 · 장보기 한 화면 (냉장고 그림 위에 장보기 '문'을 겹쳐 열고 닫는다)
    views/recipe.py   🍳 요리 추천
"""

import streamlit as st

import auth
import sample_data
import shopping_store
import ui

# 로그아웃·테스트 데이터 넣기로 예약된 화면 기억 지우기 (다른 코드가 화면 기억을 읽기 전에)
auth.clear_pending()

# 휴대폰이면 사이드바를 접어 두고, 아래쪽 메뉴 막대로 이동한다. (ui.py)
mobile = ui.is_mobile()
st.set_page_config(
    page_title="스마트 냉장고", page_icon="🧊", initial_sidebar_state="collapsed" if mobile else "auto"
)

# 앱 전체 스타일(색·글꼴은 .streamlit/config.toml) + 다크 모드·화면 폭 감시
ui.apply_style(mobile)
ui.watch()

# 로그인하지 않았으면 로그인 화면만 보여 주고 멈춘다. 로그인하면 그 사람 냉장고만 읽고 쓴다. (auth.py, storage.py)
user = auth.require_login()

# 아직 안 산 항목 개수 (휴대폰 아래 메뉴의 "장보기 3"에 쓴다)
count = shopping_store.unchecked_count(shopping_store.load())

# st.Page: 페이지 하나. url_path를 정해 두면 제목(개수)이 바뀌어도 같은 페이지로 인식된다.
fridge_page = st.Page("views/fridge.py", title="냉장고", icon="🧊", url_path="fridge", default=True)
recipe_page = st.Page("views/recipe.py", title="요리 추천", icon="🍳", url_path="recipe")

# st.navigation: 왼쪽 사이드바에 메뉴를 만들고, 고른 페이지를 실행한다.
page = st.navigation([fridge_page, recipe_page])

# 다른 페이지에 다녀와도 입력해 둔 값이 남게 한다.
# Streamlit은 화면에 없는 입력칸의 값을 지우는데, 매번 같은 값을 다시 넣어 두면 지우지 않는다.
KEEP_KEYS = ("recipe_tab", "recipe_chosen", "dish_pick", "shop_tab", "shop_name", "shop_quantity", "shop_unit")
for key in list(st.session_state.keys()):
    if key in KEEP_KEYS or key.startswith("recipe_missing_"):  # 요리 카드의 '장바구니에 담을 재료' 고르기
        st.session_state[key] = st.session_state[key]

# 다른 페이지에서 막 넘어왔는지 기억한다. (냉장고 문 열림/닫힘 효과를 넘어올 때만 보여 주려고)
st.session_state.page_changed = st.session_state.get("current_page") != page.url_path
st.session_state.current_page = page.url_path

# 휴대폰: 화면 아래쪽 메뉴 막대. 냉장고·장보기는 같은 화면이라 ?show=fridge|door 로 문을 열고 닫는다.
if mobile:
    ui.bottom_nav([
        (fridge_page, "냉장고", {"show": "fridge"}),
        (fridge_page, f"장보기{f' {count}' if count else ''}", {"show": "door"}),
        (recipe_page, "요리", None),
    ])


# ---------------------------------------------------------------
# 🧪 테스트 데이터 넣기 (사이드바 아래)
# 지금 데이터를 지우는 버튼이라 한 번 더 확인한 뒤 바꾼다.
# ---------------------------------------------------------------
def reset_to_sample():
    sample_data.load_sample()
    # 입력칸·열린 창·추천 결과 같은 화면 상태도 모두 지워서 처음 상태로 만든다. (로그인은 그대로)
    # 지우기는 다음 실행 맨 앞에서 한다. (auth.clear_pending)
    st.session_state.clear_to = {**auth.keep_keys(), "flash": (True, "🧪 테스트 데이터를 넣었어요.")}


with st.sidebar:
    st.divider()
    col_user, col_out = st.columns([3, 2], vertical_alignment="center")
    col_user.markdown(f"👤 **{user}**")
    col_out.button("로그아웃", key="log_out", type="tertiary", on_click=auth.log_out)
    if st.session_state.get("sample_ask"):
        st.warning("내 냉장고 데이터가 지워져요. 테스트 데이터로 바꿀까요?")
        col_yes, col_no = st.columns(2)
        col_yes.button("바꾸기", key="sample_yes", type="primary", on_click=reset_to_sample)
        col_no.button("취소", key="sample_no", on_click=lambda: st.session_state.pop("sample_ask", None))
    else:
        st.button(
            "🧪 테스트 데이터 넣기", key="sample_open",
            on_click=lambda: st.session_state.update(sample_ask=True),
        )

page.run()
