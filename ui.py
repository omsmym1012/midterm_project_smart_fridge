"""화면 공통 도우미 (4단계: 다크 모드·모바일 화면)

1) 다크 모드 감지
   Streamlit은 밝게/어둡게 테마를 바꿔 주지만, 직접 넣은 CSS(냉장고 그림, 메모지)는
   지금 어떤 테마인지 알 방법이 없다. 그래서 보이지 않는 작은 컴포넌트가 앱 배경색을 읽어서
   <html data-ft="dark|light"> 표시를 붙인다. CSS는 html[data-ft="dark"] 로 어두운 색을 고른다.
   (테마를 바꾸면 바로 다시 읽는다)

2) 모바일 화면 감지
   같은 컴포넌트가 화면 폭을 재서 700px보다 좁으면 "모바일"이라고 Python에 알려 준다.
   페이지들은 ui.is_mobile()로 휴대폰용 배치를 고른다.
   주소 끝에 ?view=mobile 또는 ?view=pc 를 붙이면 강제로 바꿔 볼 수 있다. (PC에서 휴대폰 화면 확인용)
"""

import streamlit as st

MOBILE_WIDTH = 700  # px. 이보다 좁으면 모바일 화면

_WATCH_JS = """
export default function (component) {
    const { data, setStateValue } = component;
    const html = document.documentElement;

    // 앱 배경색이 어두우면 다크 모드로 본다.
    function applyTheme() {
        const app = document.querySelector(".stApp");
        if (!app) return;
        const rgb = (getComputedStyle(app).backgroundColor.match(/\\d+/g) || [255, 255, 255]).map(Number);
        const light = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255;
        html.dataset.ft = light < 0.5 ? "dark" : "light";
    }
    applyTheme();
    if (!window.__ftThemeWatch) {
        // 테마를 바꾸면 .stApp의 class가 바뀐다 → 다시 읽는다.
        window.__ftThemeWatch = new MutationObserver(() => setTimeout(applyTheme, 50));
        const app = document.querySelector(".stApp");
        if (app) window.__ftThemeWatch.observe(app, { attributes: true, attributeFilter: ["class"] });
    }

    // 화면 폭이 바뀌어 모바일/PC가 달라졌을 때만 Python에 알린다. (쓸데없이 다시 그리지 않게)
    window.__ftSend = setStateValue;
    function sendWidth() {
        const mobile = window.innerWidth < data.limit;
        if (mobile !== window.__ftLastMobile) {
            window.__ftLastMobile = mobile;
            if (mobile !== data.mobile) window.__ftSend("mobile", mobile);
        }
    }
    window.__ftLastMobile = data.mobile;
    sendWidth();
    if (!window.__ftResizeWatch) {
        window.__ftResizeWatch = true;
        window.addEventListener("resize", () => sendWidth());
    }
}
"""

_watch = st.components.v2.component("ui_watch", js=_WATCH_JS)


def _on_mobile_change():
    st.session_state.ui_mobile = (st.session_state.get("ui_watch") or {}).get("mobile")


def watch():
    """감시 컴포넌트를 붙인다. (app.py에서 매번 한 번 부른다. 화면에는 보이지 않는다)"""
    _watch(
        key="ui_watch",
        data={"mobile": st.session_state.get("ui_mobile"), "limit": MOBILE_WIDTH},
        on_mobile_change=_on_mobile_change,
    )


def is_mobile():
    """지금 휴대폰 화면인지. (?view= 주소 > 잰 화면 폭 > 브라우저 종류 순서로 판단)"""
    view = st.query_params.get("view")
    if view in ("mobile", "pc"):
        st.session_state.ui_view = view  # 다른 페이지로 가도 유지
    view = st.session_state.get("ui_view")
    if view:
        return view == "mobile"
    if st.session_state.get("ui_mobile") is not None:
        return st.session_state.ui_mobile
    agent = (st.context.headers.get("User-Agent") or "").lower()
    return any(word in agent for word in ("iphone", "android", "mobile"))


# ---------------------------------------------------------------
# 앱 전체 CSS
# ---------------------------------------------------------------
BASE_CSS = """
@import url("https://fonts.googleapis.com/css2?family=Gaegu:wght@400;700&display=swap");  /* 메모지 손글씨 */
html {
    --ft-nav-bg: rgba(255, 255, 255, 0.96); --ft-nav-line: #DCE3E8;
    --ft-sub: #5B6775; --ft-expired: #D9363E;
}
html[data-ft="dark"] {
    --ft-nav-bg: rgba(18, 23, 29, 0.96); --ft-nav-line: #2A333D;
    --ft-sub: #93A0AE;
}
.block-container { padding-top: 2.5rem; padding-bottom: 3rem; }
h1 { font-size: 1.6rem !important; }
/* 맨 위 요약 문장: 보조 글자색, 기한 지난 재료만 빨간 굵은 글씨 */
.ft-summary { color: var(--ft-sub); margin: 0; }
.ft-summary b { color: var(--ft-expired); }
.ft-summary-cart b { color: inherit; }
/* 다크 모드의 밝은 파랑 버튼에는 어두운 글자 (흰 글자는 잘 안 읽힌다) */
html[data-ft="dark"] button[data-testid="stBaseButton-primary"],
html[data-ft="dark"] button[data-testid="stBaseButton-primary"] p { color: #0d1420 !important; }
.st-key-ui_watch { display: none; }
/* 머리 영역: 높이 고정, 넘치는 부분은 감춘다(스크롤 막대 없이) */
.st-key-page_head { overflow: hidden !important; padding-top: 4px; box-sizing: border-box; }
.st-key-page_head [data-testid="stCaptionContainer"] { margin-top: -0.4rem; }
/* 목록 한 줄(체크박스가 있는 줄)은 좁은 화면에서도 한 줄로 유지 */
[data-testid="stHorizontalBlock"]:has([class*="st-key-cand_chk_"]),
[data-testid="stHorizontalBlock"]:has([class*="st-key-shop_chk_"]),
[data-testid="stHorizontalBlock"]:has([class*="st-key-buy_chk_"]),
[class*="st-key-row_buttons"] [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important; gap: 0.5rem;
}
[data-testid="stHorizontalBlock"]:has([class*="_chk_"]) > div,
[class*="st-key-row_buttons"] [data-testid="stHorizontalBlock"] > div { min-width: 0 !important; }
"""

# 휴대폰 화면에만 더하는 CSS: 아래쪽 메뉴 막대, 좁은 여백, 작은 글씨
MOBILE_CSS = """
.block-container { padding: 1.2rem 0.8rem 6rem 0.8rem !important; }
h1 { font-size: 1.5rem !important; }
[data-testid="stHorizontalBlock"]:has([class*="_chk_"]) [data-testid="stCaptionContainer"] { font-size: 0.7rem; }
[data-testid="stHorizontalBlock"]:has([class*="_chk_"]) button { padding: 0 0.45rem; min-height: 2.2rem; }
[data-testid="stHorizontalBlock"]:has([class*="_chk_"]) [data-testid="stNumberInputContainer"] button { display: none; }
[data-testid="stHorizontalBlock"]:has([class*="_chk_"]) p { font-size: 0.88rem; }

/* 머리 영역의 버튼 줄은 맨 아래에 붙인다. (요약 문장이 1줄이든 2줄이든 냉장고·장보기 버튼이 같은 자리) */
.st-key-page_head > div:last-child { margin-top: auto; }

/* 아래쪽 메뉴 막대 (휴대폰 앱처럼 화면 맨 아래에 고정) */
.st-key-bottom_nav {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 999990;
    padding: 0.3rem 0.4rem calc(0.3rem + env(safe-area-inset-bottom));
    background: var(--ft-nav-bg); border-top: 1px solid var(--ft-nav-line);
    box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.08);
}
.st-key-bottom_nav [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0 !important; }
.st-key-bottom_nav [data-testid="stHorizontalBlock"] > div { min-width: 0 !important; flex: 1 1 0 !important; }
.st-key-bottom_nav a {
    flex-direction: column; gap: 0; padding: 0.25rem 0 !important; justify-content: center;
    width: 100%; border-radius: 0.6rem;
}
.st-key-bottom_nav a p { font-size: 0.68rem !important; line-height: 1.2; }
.st-key-bottom_nav a span { font-size: 1.25rem; }
"""


def apply_style(mobile):
    """앱 전체 CSS를 넣는다."""
    st.html(f"<style>{BASE_CSS}{MOBILE_CSS if mobile else ''}</style>")


def bottom_nav(pages):
    """휴대폰 화면 아래쪽 메뉴 막대. pages: [(st.Page, 짧은 이름, 주소에 붙일 값 또는 None), ...]

    냉장고·장보기는 같은 페이지라서 ?show=fridge|door 로 어느 쪽(문 열림/닫힘)을 볼지 알려 준다.
    """
    icons = {"door": "🛒"}
    with st.container(key="bottom_nav"):
        for col, (page, label, params) in zip(st.columns(len(pages)), pages):
            icon = icons.get((params or {}).get("show"), page.icon)
            col.page_link(page, label=label, icon=icon, width="stretch", query_params=params)


# ---------------------------------------------------------------
# 머리 영역: 제목 아래 요약·버튼 줄
# 냉장고·장보기 페이지가 같은 높이의 머리 영역을 쓰면, 그 아래 냉장고 그림과 닫힌 문이
# 화면의 같은 자리에서 시작한다. (페이지를 옮겨도 냉장고가 제자리에 있는 것처럼 보이게)
# ---------------------------------------------------------------
HEAD_HEIGHT = 100         # px (PC)
HEAD_HEIGHT_MOBILE = 96   # px (휴대폰)


def page_head(mobile):
    """높이가 고정된 머리 영역 컨테이너를 돌려준다. (with ui.page_head(MOBILE): ...)"""
    return st.container(
        key="page_head", height=HEAD_HEIGHT_MOBILE if mobile else HEAD_HEIGHT, border=False, gap="small"
    )


def show_flash():
    """직전 작업의 결과 메시지를 화면 아래 알림(토스트)으로 보여 준다.

    메시지 상자가 화면 중간에 끼어들면 냉장고 그림이 아래로 밀리므로, 자리를 차지하지 않는 알림을 쓴다.
    """
    if "flash" in st.session_state:
        ok, message = st.session_state.pop("flash")
        st.toast(message, icon="✅" if ok else "⚠️", duration="long")
