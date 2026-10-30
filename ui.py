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

import json
from datetime import date

import streamlit as st


MOBILE_WIDTH = 700  # px. 이보다 좁으면 모바일 화면

_WATCH_JS = """
export default function (component) {
    const { data, setStateValue, setTriggerValue } = component;
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

    // 새로고침 뒤 한 번: 이 브라우저에 저장해 둔 팝업 입력 내용(save_draft)을 Python에 보낸다. (로그인 뒤에만 draftKey가 온다)
    if (data.draftKey) {
        let saved = "";
        try { saved = localStorage.getItem(data.draftKey) || ""; } catch (e) {}
        setTriggerValue("draft", saved);
    }

    // 검색칸에서 목록에 없는 글자를 치면 Streamlit이 "Add: 김치 볶음밥"(영어)을 보여 준다. → "🔍 김치 볶음밥 찾기"
    if (!window.__ftAddWatch) {
        window.__ftAddWatch = new MutationObserver(() => {
            document.querySelectorAll('[role="option"]').forEach((option) => {
                const leaf = [...option.querySelectorAll("*")].concat(option).find(
                    (node) => node.childElementCount === 0 && node.textContent.startsWith("Add: "));
                if (leaf) leaf.textContent = "🔍 " + leaf.textContent.slice(5) + " 찾기";
            });
        });
        window.__ftAddWatch.observe(document.body, { childList: true, subtree: true, characterData: true });
    }
}
"""

_watch = st.components.v2.component("ui_watch", js=_WATCH_JS)


def _on_mobile_change():
    st.session_state.ui_mobile = (st.session_state.get("ui_watch") or {}).get("mobile")


def watch():
    """감시 컴포넌트를 붙인다. (app.py에서 매번 한 번 부른다. 화면에는 보이지 않는다)"""
    state = st.session_state
    _watch(
        key="ui_watch",
        data={
            "mobile": state.get("ui_mobile"), "limit": MOBILE_WIDTH,
            # 로그인했고 아직 되살리지 않았을 때만 브라우저 임시 저장을 읽어 오게 한다.
            "draftKey": _draft_key() if state.get("user") and not state.get("draft_restored") else None,
        },
        on_mobile_change=_on_mobile_change, on_draft_change=_on_draft,
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
.block-container { padding-top: 3rem; padding-bottom: 3rem; }  /* 위쪽 Streamlit 막대(60px)에 전환 버튼이 가리지 않게 */
h1 { font-size: 1.6rem !important; }
/* 맨 위 요약 문장: 보조 글자색, 기한 지난 재료만 빨간 굵은 글씨 */
.ft-summary { color: var(--ft-sub); margin: 0; }
.ft-summary b { color: var(--ft-expired); }
.ft-summary span { white-space: nowrap; }  /* 묶음 중간(단어 가운데)에서 줄이 바뀌지 않게 */
.ft-summary-cart b { color: inherit; }
/* 다크 모드의 밝은 파랑 버튼에는 어두운 글자 (흰 글자는 잘 안 읽힌다) */
html[data-ft="dark"] button[data-testid="stBaseButton-primary"]:not(:disabled),
html[data-ft="dark"] button[data-testid="stBaseButton-primary"]:not(:disabled) p { color: #0d1420 !important; }
/* 누를 수 없는(비활성) 파랑 버튼은 배경이 어두워지므로 흐린 밝은 글자로 */
html[data-ft="dark"] button[data-testid="stBaseButton-primary"]:disabled,
html[data-ft="dark"] button[data-testid="stBaseButton-primary"]:disabled p { color: rgba(228, 234, 240, 0.45) !important; }
.st-key-ui_watch, [class*="st-key-draft_saver_"] { display: none; }
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


# ---------------------------------------------------------------
# 팝업에 적던 내용 임시 저장 (5단계)
# 새로고침하면 화면 기억(session_state)이 비므로, 팝업 입력칸 값을 이 브라우저(localStorage)에 적어 두고
# 새로고침 뒤 다시 채운다. 인터넷으로 저장하지 않아서 빠르다. (다른 기기에서는 이어 쓸 수 없다)
# 팝업 안에서 값을 바꾸면 팝업만 다시 그려지므로 팝업마다 save_draft(where)를 부른다.
# ---------------------------------------------------------------
_DRAFT_JS = """
export default function (component) {
    const { data } = component;
    try { localStorage.setItem(data.key, data.draft); } catch (e) {}  // 저장소를 못 쓰는 브라우저면 그냥 넘어간다.
}
"""
_draft_saver = st.components.v2.component("draft_saver", js=_DRAFT_JS)
# 저장할 입력칸 이름(앞부분). add_: 재료 추가, multi_: 재료 사용, bulk_: 장바구니 담기, receipt_draft: 영수증 표,
DRAFT_PREFIXES = ("add_", "multi_amt_", "multi_act_", "bulk_", "single_id", "receipt_draft",
                  "shop_name", "shop_quantity", "shop_unit")  # shop_: 장바구니 직접 추가
DRAFT_SKIP = ("add_msg",)  # 한 번 보여 주고 끝나는 알림은 남기지 않는다.
POPUP_KEYS = ("add_open", "multi_open", "single_id", "receipt_open", "bulk_rebuy", "shop_add_open")


def _encode(value):
    """날짜는 JSON에 그대로 못 넣으므로 {"__date__": "2026-10-30"} 꼴로 바꾼다."""
    return json.loads(json.dumps(value, default=lambda v: {"__date__": v.isoformat()[:10]}))


def _decode(obj):
    return date.fromisoformat(obj["__date__"]) if set(obj) == {"__date__"} else obj


def _draft_key():
    return f"ft_draft_{st.session_state.get('user')}"  # 같은 브라우저에서도 사람마다 따로


def save_draft(where):
    """열린 팝업의 입력칸 값을 브라우저에 저장한다. 팝업이 없으면 비운다.

    where: 부르는 곳 이름 (팝업마다 다른 이름이어야 한 화면에 여러 번 그려도 겹치지 않는다)
    """
    state = st.session_state
    if not state.get("draft_restored"):
        return  # 새로고침 뒤 저장된 내용을 먼저 읽어 와야 한다. (읽기 전에 빈 내용으로 덮어쓰지 않게)
    draft = {}
    if any(state.get(key) for key in POPUP_KEYS):
        draft = _encode({
            key: value for key, value in state.items()
            if str(key).startswith(DRAFT_PREFIXES) and key not in DRAFT_SKIP
        })
    _draft_saver(key=f"draft_saver_{where}", data={"key": _draft_key(), "draft": json.dumps(draft, ensure_ascii=False)})


def _on_draft():
    """새로고침 뒤 한 번: 브라우저에 저장해 둔 팝업 입력칸 값을 다시 채운다."""
    state = st.session_state
    state.draft_restored = True
    try:
        draft = json.loads((state.get("ui_watch") or {}).get("draft") or "{}", object_hook=_decode)
    except ValueError:
        return
    state.update(draft)
    if state.get("receipt_open") and state.get("receipt_draft"):
        state.receipt_rows = state.receipt_draft  # 영수증 표는 고친 내용까지 그대로
