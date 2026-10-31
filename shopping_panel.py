"""🛒 장보기 패널 (냉장고 화면 안에서 쓰는 '닫힌 냉장고 문')

views/fridge.py가 냉장고 그림 위에 같은 크기의 "문" 컨테이너를 겹쳐 두고, render()로 이 안을 채운다.
문이 닫히면(장보기) 보이고, 열리면(냉장고) 경첩을 축으로 돌아가며 사라진다.

1) 다시 사기 탭: 소진·폐기한 재료, 기한 지난/임박 재료, 살 때가 된 재료를 골라 한 번에 담기 / 안 담기
2) 장바구니 탭   : 장바구니 목록(산 재료 체크, 수량 수정, 삭제). 직접 추가는 머리 영역 [＋ 직접 추가] 팝업
3) 냉장고 넣기 : 체크한 항목의 유통기한을 고르고 한 번에 냉장고에 넣기
"""

from datetime import date

import streamlit as st

import classifier
import fridge_store
import receipt_panel
import shopping_store as shop
import ui


# ---------------------------------------------------------------
# 디자인: 냉장고 문 + 자석으로 붙여 둔 메모지
# - 문(.st-key-fridge_door)은 냉장고 그림과 같은 자리·같은 크기로 겹쳐 둔다.
# - 열림/닫힘은 CSS transition으로 부드럽게 돈다. (문 요소는 그대로 두고 모양만 바꿔서)
# - 다크 모드 색은 ui.py가 붙인 html[data-ft="dark"]로 고른다.
# ---------------------------------------------------------------
DOOR_CSS = """
html {
    --door-body: linear-gradient(140deg, #fbfcfd 0%, #e9eef2 60%, #dbe2e8 100%);
    --door-edge: #DCE3E8;
    --door-handle: linear-gradient(90deg, #aab5bb, #eef2f3, #9aa6ac);
    --note-paper: #fffdf4;
    --note-sub: #5B6775;
    --note-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    --door-accent: #2456C8;
}
html[data-ft="dark"] {
    --door-body: linear-gradient(140deg, #3a444d 0%, #2c343c 60%, #232a31 100%);
    --door-edge: #2A333D;
    --door-handle: linear-gradient(90deg, #5d6a71, #9aa7ad, #4f5a60);
    --note-paper: #262a2e;
    --note-sub: #93A0AE;
    --note-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
    --door-accent: #6E9BFF;
}
/* 냉장고 그림과 문을 담는 무대: 문은 이 안에서 냉장고 그림 위에 겹쳐진다. */
.st-key-fridge_stage { position: relative; perspective: 1800px; }
/* 문: 냉장고 몸체와 같은 자리(맨 위)·같은 크기 */
.st-key-fridge_door {
    position: absolute !important; top: 0; left: 0; right: 0; z-index: 20;
    width: auto !important;   /* Streamlit이 붙이는 폭 100%를 풀어서 left·right로 폭을 정한다. */
    box-sizing: border-box;
    height: HEIGHTpx;
    background: var(--door-body);
    border: 1px solid var(--door-edge);
    border-radius: 14px;   /* 냉장고 몸체와 같은 둥글기 */
    padding: 16px 26px 30px 18px;
    box-shadow: 0 12px 28px rgba(30, 45, 50, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.45);
    transform-origin: left center;   /* 왼쪽 경첩 */
    flex-wrap: nowrap !important;
}
@keyframes door-close {
    0%   { transform: rotateY(-100deg); }
    70%  { transform: rotateY(3deg); }
    100% { transform: rotateY(0deg); }
}
/* 문 손잡이: 진짜 버튼(누르면 문이 열린다)을 손잡이 모양으로 */
.st-key-door_handle {
    position: absolute !important; right: -8px; top: 70px; width: 16px !important; z-index: 2;
}
.st-key-door_handle button {
    width: 16px; min-width: 0; height: 150px; min-height: 0; padding: 0;
    border-radius: 8px; border: 1px solid var(--door-edge);
    background: var(--door-handle); box-shadow: 2px 4px 8px rgba(0, 0, 0, 0.3);
    color: transparent; font-size: 0; cursor: pointer;
}
.st-key-door_handle button:hover { filter: brightness(1.08); }
/* 문 안의 탭: 메모지 내용이 길면 메모지 안에서 위아래로 넘겨 본다. */
.st-key-fridge_door [data-testid="stTabs"] { flex: 1; min-height: 0; }
.st-key-fridge_door [data-testid="stTabs"] > div { height: 100%; display: flex; flex-direction: column; }
.st-key-fridge_door [data-testid="stTabPanel"] { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.st-key-fridge_door [data-testid="stTabPanel"][inert] { display: none; }
.st-key-fridge_door [data-testid="stTabPanel"] > [data-testid="stVerticalBlock"] {
    flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; padding-right: 6px;
}
/* 탭 이름: 냉장고 문에 붙은 동그란 자석 버튼처럼 */
.st-key-fridge_door [role="tablist"] { gap: 8px; border: none; box-shadow: none; overflow: visible; }
.st-key-fridge_door [data-testid="stTab"] {
    background: var(--note-paper); border-radius: 999px; padding: 5px 14px; height: auto;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.18);
}
.st-key-fridge_door [data-testid="stTab"][aria-selected="true"] {
    box-shadow: 0 0 0 2px var(--door-accent), 0 2px 5px rgba(0, 0, 0, 0.18);
}
.st-key-fridge_door .react-aria-SelectionIndicator { display: none; }
/* 탭 내용: 자석으로 붙여 둔 줄 노트 */
.st-key-fridge_door [data-testid="stTabPanel"] {
    position: relative;
    margin-top: 14px;
    padding: 22px 16px 14px 16px;
    background: var(--note-paper);   /* 줄 없는 메모지 */
    border-radius: 2px;
    box-shadow: var(--note-shadow);
    transform: rotate(-1deg);
}
/* 메모지 위 글씨는 손글씨(Gaegu): 재료 이름·본문.
   작은 안내 글씨(매장 코너·최저가 등)와 입력칸·버튼 글자는 또렷한 기본 글꼴 그대로 둔다. */
.st-key-fridge_door [data-testid="stTabPanel"] [data-testid="stMarkdown"] p strong,
.st-key-fridge_door [data-testid="stTabPanel"] [data-testid="stMarkdown"] p del {
    font-family: "Gaegu", cursive; font-size: 1.3rem; line-height: 1.3; font-weight: 700;
}
.st-key-fridge_door [data-testid="stTabPanel"] button [data-testid="stMarkdownContainer"] p,
.st-key-fridge_door [data-testid="stTabPanel"] label [data-testid="stMarkdownContainer"] p {
    font-family: inherit; font-size: inherit; line-height: inherit;
}
/* 빨간 자석 */
.st-key-fridge_door [data-testid="stTabPanel"]::before {
    content: ""; position: absolute; top: -11px; left: 50%; width: 26px; height: 26px; margin-left: -13px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, #ff9a8f, #e5484d 55%, #a8262b);
    box-shadow: 0 3px 6px rgba(0, 0, 0, 0.3);
}
"""
# 닫힘(장보기): 문이 정면. 열림(냉장고): 경첩을 축으로 돌아가 사라진다. 바뀔 때 transition으로 부드럽게.
DOOR_CLOSED_CSS = """
.st-key-fridge_door {
    transform: rotateY(0deg); visibility: visible; opacity: 1;
    transition: transform 0.85s cubic-bezier(0.3, 0.75, 0.3, 1), opacity 0.3s, visibility 0s;
}
"""
DOOR_OPEN_CSS = """
.st-key-fridge_door {
    transform: rotateY(-100deg); visibility: hidden; opacity: 0; pointer-events: none;
    transition: transform 0.85s cubic-bezier(0.55, 0, 0.35, 1), opacity 0.35s 0.5s, visibility 0s 0.85s;
}
"""
DOOR_MOBILE_CSS = """
.st-key-fridge_door { padding: 12px 18px 22px 10px; }
.st-key-door_handle { right: -6px; top: 60px; width: 12px !important; }
.st-key-door_handle button { width: 12px; height: 110px; }
.st-key-fridge_door [data-testid="stTabPanel"] { padding: 22px 8px 10px 20px; }
.st-key-fridge_door [data-testid="stTab"] { padding: 4px 10px; }
"""

# 문 안의 탭 3개 (머리 영역의 지름길 버튼도 이 이름으로 탭을 고른다)
TAB_REBUY, TAB_CART, TAB_PUT = "🔁 다시 사기", "🛒 장바구니", "🧊 냉장고 넣기"


def active_tab():
    """지금 보여 줄 장보기 탭. 냉장고 넣기 탭은 [구매]한 재료가 있을 때만 갈 수 있다. (탭을 그리기 전에 부른다)"""
    state = st.session_state
    if state.get("goto_tab"):  # 머리 영역 [냉장고 넣기]·장바구니 [구매]로 고른 탭
        state.shop_tab = state.pop("goto_tab")
    if state.get("shop_tab") == TAB_PUT and not shop.bought_items(shop.load()):
        state.shop_tab = TAB_CART
    return state.get("shop_tab")


def door_css(closed, height, mobile, entering, right=0):
    """문 CSS. closed: 문이 닫혀 있는지(장보기), entering: 다른 페이지에서 막 들어왔는지(닫히는 효과)

    right: 문 오른쪽을 비울 폭(px). PC에서는 냉장고 옆 '새 재료' 봉투 자리만큼 비워서 냉장고 몸체에만 겹친다.
    """
    css = DOOR_CSS.replace("HEIGHT", str(height))
    css += f".st-key-fridge_door {{ right: {right}px; }}"
    css += DOOR_CLOSED_CSS if closed else DOOR_OPEN_CSS
    if closed and entering:
        css += ".st-key-fridge_door { animation: door-close 0.9s cubic-bezier(0.3, 0.7, 0.3, 1); }"
    if mobile:
        css += DOOR_MOBILE_CSS
    return f"<style>{css}</style>"


def render(head, door, mobile, show_head):
    """장보기 화면을 그린다.

    head: 머리 영역 컨테이너 (show_head=True일 때만 요약·바로 가기를 그린다)
    door: 냉장고 문 컨테이너 (탭 3개를 그린다)
    """
    MOBILE = mobile
    # 화면이 다시 그려질 때마다 파일에서 최신 데이터를 읽어 온다.
    fridge_items = fridge_store.load_items()
    data = shop.load()


    # ---------------------------------------------------------------
    # 공통 도우미
    # ---------------------------------------------------------------
    def finish(ok, message):
        """결과 메시지를 기억해 두고 화면을 새로 그린다. (메시지는 다음 화면 맨 위에 표시)"""
        if message:  # 빈 메시지면 알림 없이 다시 그리기만 한다.
            st.session_state.flash = (ok, message)
        st.rerun()


    def select_all_buttons(name, set_all):
        """[전체 선택] [전체 해제] 글자 버튼 한 줄. set_all(True/False)로 체크 칸을 한꺼번에 바꾼다."""
        with st.container(horizontal=True, gap="small"):
            st.button("전체 선택", key=f"{name}_all", type="tertiary", on_click=set_all, args=(True,))
            st.button("전체 해제", key=f"{name}_none", type="tertiary", on_click=set_all, args=(False,))


    def known_info(name):
        """이 재료의 분류·단위를 알아낸다.

        냉장고(또는 "다 씀" 기록)에 같은 이름이 있으면 그 값을 쓰고, 없으면 자동 분류한다.
        """
        key = fridge_store.normalize_name(name)
        for item in reversed(fridge_items):  # 최근에 넣은 기록부터
            if fridge_store.normalize_name(item["name"]) == key and item.get("category"):
                return {
                    "category": item["category"], "storage": item["storage"],
                    "unit": item["unit"], "tip": item.get("tip", ""),
                }
        return classifier.classify(name)


    # 직전 작업의 결과 메시지 표시 (한 번 보여 주고 지운다)
    # ---------------------------------------------------------------
    # 머리 영역(높이 고정): 요약 + 영수증·구매 기록 바로 가기
    # 냉장고 페이지와 높이가 같아서, 아래 닫힌 문이 냉장고 그림과 같은 자리에 온다.
    # ---------------------------------------------------------------
    candidates = shop.candidates(fridge_items, data)
    to_buy = shop.unchecked_count(data)
    bought_count = len(shop.bought_items(data))
    # 요약 문장 (냉장고 화면의 요약과 같은 모양: ui.py의 .ft-summary)
    parts = [f"<b>살 것 {to_buy}개</b>" if to_buy else "살 것이 없어요"]
    if bought_count:
        parts.append(f"산 것 {bought_count}개")
    if candidates:
        parts.append(f"다시 사기 {len(candidates)}개")
    summary = f'<p class="ft-summary ft-summary-cart">{", ".join(parts)}</p>'

    if show_head:
        with head:
            # 냉장고 화면의 머리 영역과 같은 배치·같은 버튼 크기로 그려서, 문을 여닫을 때 위쪽도 자연스럽게 바뀐다.
            #   PC: 오른쪽에 [＋ 직접 추가][🧾 영수증] 한 줄, 그 아래 [냉장고 넣기] ([＋ 재료 추가][🧾 영수증]/[사용] 자리)
            #   휴대폰: 버튼 3개 가로
            # 두 버튼은 문 안의 탭으로 바로 가는 지름길이다.
            to_cart = lambda: st.session_state.update(shop_add_open=True)  # [＋ 직접 추가] 팝업 열기
            to_put = lambda: st.session_state.update(goto_tab=TAB_PUT)
            put_label = f"냉장고 넣기 ({bought_count})" if bought_count else "냉장고 넣기"
            if MOBILE:
                st.markdown(summary, unsafe_allow_html=True)
                with st.container(key="row_buttons"):
                    col_add, col_receipt, col_put = st.columns([1, 1.1, 1])
            else:
                col_summary, col_buttons = st.columns([3.2, 2], vertical_alignment="center")
                col_summary.markdown(summary, unsafe_allow_html=True)
                col_summary.caption("담은 재료를 [구매]하면 '냉장고 넣기'에서 한 번에 냉장고로 들어가요.")
                col_add, col_receipt = col_buttons.columns(2, gap="small")
                col_put = col_buttons
            col_add.button("＋ 직접 추가", key="head_add", width="stretch", on_click=to_cart)
            col_receipt.button("🧾 영수증", key="head_receipt", width="stretch", on_click=receipt_panel.open_receipt)
            # 이미 '냉장고 넣기' 탭을 보고 있으면 옮겨 갈 필요가 없으므로 버튼을 숨긴다. (방금 누른 경우도 포함)
            if active_tab() != TAB_PUT:
                col_put.button(put_label, key="head_put", type="primary", width="stretch",
                               disabled=not bought_count, on_click=to_put)


    with door:
        # 손잡이(오른쪽 세로 막대)를 누르면 문이 열린다. → 냉장고 화면
        st.button("문 열기", key="door_handle",
                  on_click=lambda: st.session_state.update(home_view="fridge"))

        # ---------------------------------------------------------------
        # 탭 3개: 다시 사기 / 장바구니(리스트 + 직접 추가) / 냉장고 넣기
        # key를 주면 버튼을 눌러 화면이 다시 그려져도 보던 탭이 유지된다.
        # ---------------------------------------------------------------
        active_tab()
        if not bought_count:
            # [구매]한 재료가 없으면 '냉장고 넣기' 탭은 흐리게, 누를 수 없게 (active_tab이 들어가도 장바구니로 돌린다)
            st.html("""<style>.st-key-shop_tab [role="tab"]:nth-child(3)
                {opacity: 0.35; pointer-events: none;}</style>""")
        # on_change="rerun": 고른 탭을 st.session_state.shop_tab으로 읽고 바꿀 수 있게 한다.
        tab_rebuy, tab_cart, tab_put = st.tabs(
            [TAB_REBUY, TAB_CART, TAB_PUT], key="shop_tab", on_change="rerun"
        )

        with tab_rebuy:
            # ---------------------------------------------------------------
            # 1) 다시 사기 (추천 목록)
            # ---------------------------------------------------------------
            if not candidates:
                st.caption("추천할 재료가 없어요.")
            else:
                # 후보를 한 줄씩: [선택] 이름·이유 | 수량 입력칸(−/＋) | 단위
                # 수량은 칸을 한 번 눌러 바로 고치거나 −/＋로 바꾼다. 단위는 냉장고에 있던 단위로 고정이다.
                # 이유별로 묶어서 제목을 붙이고, 줄마다 색 배지로도 구분한다. (기한 지남·폐기 → 곧 지남 → 다 씀 순서)
                # 폐기한 재료(다 쓴 기록 중 폐기)는 기한 지난 재료와 같은 묶음에 둔다.
                GROUP_TITLE = {
                    "expired": "🚫 기한 지남 · 폐기",
                    "soon": f"⏰ 곧 지나요 ({fridge_store.SOON_DAYS}일 이내)",
                    "used": "🫙 소진한 재료",
                }
                ORDER = list(GROUP_TITLE)
                select_all_buttons("cand", lambda on: st.session_state.update(
                    {f"cand_chk_{c['keys'][0]}": on for c in candidates}))

                def group_of(candidate):
                    """반환: (묶음, 배지, 날짜·수량 글자). detail 예: 기한 지남 · 10/27 1팩 / 폐기 · 10/28"""
                    reason, _, when = candidate["detail"].partition(" · ")
                    if candidate["kind"] == shop.SOURCE_EXPIRED:
                        return "expired", ":red-badge[기한 지남]", when
                    if candidate["kind"] == shop.SOURCE_SOON:
                        return "soon", ":orange-badge[곧 지남]", when
                    if reason == "폐기":
                        return "expired", ":red-badge[폐기]", when
                    return "used", ":gray-badge[소진]", when

                chosen = []
                last_title = None
                for candidate in sorted(candidates, key=lambda c: ORDER.index(group_of(c)[0])):
                    group, badge, when = group_of(candidate)
                    title = GROUP_TITLE[group]
                    if title != last_title:
                        st.markdown(f"**{title}**")
                        last_title = title
                    key = candidate["keys"][0]  # 입력칸 key를 구분하기 위한 값
                    col_chk, col_name, col_qty, col_unit = st.columns([0.5, 3, 1.6, 0.7], vertical_alignment="center")
                    picked = col_chk.checkbox(
                        f"{candidate['name']} 선택", key=f"cand_chk_{key}", label_visibility="collapsed"
                    )
                    col_name.markdown(f"**{candidate['name']}** {badge} :gray[{when}]")
                    quantity = col_qty.number_input(
                        f"{candidate['name']} 수량", min_value=0.1, value=float(candidate.get("quantity", 1)), step=1.0, format="%g",
                        key=f"cand_qty_{key}", label_visibility="collapsed",
                    )
                    col_unit.write(candidate["unit"])
                    if picked:
                        chosen.append((candidate, quantity))

                with st.container(key="row_buttons_cand"):
                    col_add, col_skip, _ = st.columns([1, 1, 0.01 if MOBILE else 2])
                if col_add.button("담기", type="primary", key="cand_add", disabled=not chosen, width="stretch"):
                    added, already = [], []
                    for candidate, quantity in chosen:
                        ok, _ = shop.add_item(data, candidate["name"], quantity, candidate["unit"], candidate["kind"])
                        shop.mark_handled(data, candidate["keys"])
                        (added if ok else already).append(candidate["name"])
                    finish(False, f"이미 장바구니에 있어요: {', '.join(already)}" if already else "")
                if col_skip.button("안 담기", key="cand_skip", disabled=not chosen, width="stretch"):
                    for candidate, _ in chosen:
                        shop.mark_handled(data, candidate["keys"])
                    finish(True, "")


        with tab_cart:
            # ---------------------------------------------------------------
            # 2) 장바구니 (장보기 리스트)
            # ---------------------------------------------------------------
            # 탭 이름이 이미 '장바구니'라서 따로 제목을 달지 않는다.

            def on_check_change(item_id):
                """체크박스(담았어요)를 누르면 바로 저장한다. 산 것은 [구매]를 눌러야 된다."""
                # 테스트 데이터 넣기·로그아웃으로 화면 기억을 지운 직후엔 값이 없을 수 있어서 건너뛴다.
                if f"shop_chk_{item_id}" in st.session_state:
                    shop.set_checked(data, item_id, st.session_state[f"shop_chk_{item_id}"])


            def on_qty_change(item_id):
                """수량을 고치면 바로 저장한다. (냉장고 넣기 탭에 이 수량으로 들어간다)"""
                if f"shop_qty_{item_id}" in st.session_state:  # (위와 같은 이유)
                    shop.set_quantity(data, item_id, st.session_state[f"shop_qty_{item_id}"])


            in_cart = [item for item in data["items"] if not item.get("bought")]  # [구매]한 것은 냉장고 넣기 탭에
            if not in_cart:
                st.info("장바구니가 비어 있어요.")
            else:
                # 진행도: 몇 개 중 몇 개를 담았는지 막대로 보여 준다.
                done = len(shop.checked_items(data))
                total = len(in_cart)
                st.progress(done / total, text=f"{total}개 중 {done}개 담았어요")

                def check_all(on):
                    for item in in_cart:
                        item["checked"] = on
                        st.session_state[f"shop_chk_{item['id']}"] = on
                    shop.save(data)

                st.caption("담은 재료에 체크하고 [구매]를 누르세요.")  # 체크 칸에 글자가 없어서 한 줄 안내
                select_all_buttons("cart", check_all)

            # 장바구니 체크박스를 [삭제] 버튼과 비슷한 크기로 키운다.
            # key가 shop_chk_로 시작하는 체크박스에만 st-key-shop_chk_... 이름표가 붙어서 그것만 고른다.
            st.html(
                """<style>
                [class*="st-key-shop_chk_"] label > div:first-of-type {
                    width: 2rem; height: 2rem; border-radius: 0.4rem;
                }
                [class*="st-key-shop_chk_"] label > div:first-of-type svg {
                    width: 1.3rem; height: 1.3rem;
                }
                /* [🌐 담기]: 작은 글씨 */
                [class*="st-key-shop_web_"] { flex-wrap: nowrap; align-items: center; }
                [class*="st-key-shop_web_"] p { font-size: 0.8rem; white-space: nowrap; margin: 0; }
                [class*="st-key-shop_web_"] button { min-height: 0; padding: 0; }
                </style>"""
            )

            # 안 담은 재료를 위에, 담은(체크한) 재료를 아래에 둔다. 두 묶음 사이에는 구분선
            # 안 산 재료는 요리별로 묶는다: 직접 담은 재료 먼저, 그다음 요리 추천에서 담은 요리마다 제목(🍳 요리 이름)
            # 두 요리에 같이 쓰는 재료는 먼저 담은 요리 묶음에 두고 '○○에도 써요'를 붙인다.
            todo = [item for item in in_cart if not item["checked"]]
            got = [item for item in in_cart if item["checked"]]
            dish_order = list(dict.fromkeys(item["dishes"][0] for item in todo if item.get("dishes")))
            todo.sort(key=lambda item: dish_order.index(item["dishes"][0]) + 1 if item.get("dishes") else 0)
            last_dish = None
            for item in todo + got:
                if got and item is got[0] and todo:
                    st.caption("✔ 담은 재료")  # 안 담은 재료와 담은 재료 사이 구분
                dish = (item.get("dishes") or [None])[0] if not item["checked"] else None
                if dish and dish != last_dish:
                    st.markdown(f"**🍳 {dish}**")
                last_dish = dish
                # 한 줄: 이름 | [🌐 담기] | 수량 입력칸 | 단위(고정) | 체크박스(산 재료면 v) | 삭제
                if MOBILE:
                    # 휴대폰: 이름 아래에 [🌐 담기] | 수량 | 단위 | 체크 | 🗑
                    col_name, col_qty, col_unit, col_chk, col_del = st.columns(
                        [2.1, 1.3, 0.85, 0.55, 0.6], vertical_alignment="center"
                    )
                    col_web = col_name
                else:
                    col_name, col_web, col_qty, col_unit, col_chk, col_del = st.columns(
                        [1.4, 1.4, 1.6, 0.7, 0.5, 1], vertical_alignment="center"
                    )
                # 담은(체크한) 재료는 초록 글씨에 🛒. 인터넷으로 살 재료는 이름 앞에 🌐
                web = "🌐 " if item.get("online") else ""
                if item["checked"]:
                    col_name.markdown(f":green[🛒 {web}**{item['name']}**]")  # 담은 재료: 초록 + 🛒 (아직 구매 전)
                else:
                    col_name.markdown(f"{web}**{item['name']}**")
                if not item["checked"]:
                    # [🌐 담기·빼기]: 인터넷 구매 목록에 넣기·빼기
                    with col_web.container(horizontal=True, gap="small", key=f"shop_web_{item['id']}"):
                        st.button(
                            "🌐 빼기" if item.get("online") else "🌐 담기", key=f"shop_online_{item['id']}",
                            type="tertiary", on_click=shop.set_online, args=(data, item["id"], not item.get("online")),
                        )
                col_qty.number_input(
                    f"{item['name']} 수량", min_value=0.1, value=float(item["quantity"]), step=1.0, format="%g",
                    key=f"shop_qty_{item['id']}", on_change=on_qty_change, args=(item["id"],),
                    label_visibility="collapsed",
                )
                col_unit.write(item["unit"])
                # 체크박스 글자는 숨기고 네모 칸만 보여 준다. (label_visibility="collapsed")
                col_chk.checkbox(
                    f"{item['name']} 담았어요",
                    value=item["checked"],
                    key=f"shop_chk_{item['id']}",
                    on_change=on_check_change,
                    args=(item["id"],),
                    label_visibility="collapsed",
                )
                delete_label = ":material/delete:" if MOBILE else "삭제"
                if col_del.button(delete_label, key=f"shop_del_{item['id']}", help="삭제"):
                    shop.remove_items(data, [item["id"]])
                    finish(True, "")
                if item.get("advice") and not item["checked"]:
                    st.caption(f"🧮 {item['advice']}")  # 구매 적정량 추천 이유 (줄 아래에 한 줄로)
                if len(item.get("dishes", [])) > 1 and not item["checked"]:
                    st.caption(f"🍳 {', '.join(item['dishes'][1:])}에도 써요")


            # [구매]: 담은 재료를 산 것으로 바꾸고 '냉장고 넣기' 탭으로 넘어간다.
            if got and st.button(f"구매 ({len(got)})", type="primary", key="shop_buy"):
                shop.buy_checked(data)
                st.session_state.goto_tab = TAB_PUT
                st.rerun()

            # ---------------------------------------------------------------
            # 🌐 인터넷 구매 목록: [🌐 인터넷으로]를 누른 재료 (장바구니에도 그대로 남아 있다)
            # ---------------------------------------------------------------
            web_items = [item for item in todo if item.get("online")]
            if web_items:
                st.markdown(f"**🌐 인터넷 구매 ({len(web_items)})**")
                with st.container(border=True, key="shop_web_list"):
                    for item in web_items:
                        qty = fridge_store.format_quantity(item["quantity"], item["unit"])
                        st.markdown(f"{item['name']} {qty}")




        with tab_put:
            # ---------------------------------------------------------------
            # 4) 냉장고 넣기: 장바구니에서 [구매]한 재료를 확인하고 한 번에 냉장고에 넣기
            #    새 재료 봉투에서 이 화면 쪽으로 끌어 온 재료도 여기로 온다. (views/fridge.py on_to_put)
            # ---------------------------------------------------------------
            bought = shop.bought_items(data)
            if not bought:
                st.caption("장바구니에서 담은 재료를 [구매]하면 여기에 나와요.")
            else:
                st.caption("유통기한을 비워 두면 '기한 없음'으로 들어가요. 넣지 않을 재료는 체크를 풀어 주세요.")

                select_all_buttons("buy", lambda on: st.session_state.update(
                    {f"buy_chk_{item['id']}": on for item in bought}))
                # 한 줄씩: [넣기] 이름·수량(장바구니에서 정한 그대로) | 유통기한 날짜칸
                rows = []
                for item in bought:
                    col_chk, col_name, col_date = st.columns([0.5, 3, 2.5], vertical_alignment="center")
                    put = col_chk.checkbox(
                        f"{item['name']} 넣기", value=True, key=f"buy_chk_{item['id']}", label_visibility="collapsed"
                    )
                    col_name.markdown(
                        f"**{item['name']}** {fridge_store.format_quantity(item['quantity'], item['unit'])}"
                    )
                    # 처음에는 날짜를 비워 둔다. (비워 두면 기한 없음) 봉투에서 끌어 온 재료는 원래 기한을 채워 둔다.
                    expiry = col_date.date_input(
                        f"{item['name']} 유통기한", value=date.fromisoformat(item["expiry"]) if item.get("expiry") else None,
                        key=f"buy_exp_{item['id']}",
                        label_visibility="collapsed", format="YYYY-MM-DD",
                    )
                    rows.append((item, put, expiry))

                if st.button("완료", type="primary", key="shop_done"):
                    separate = []
                    with st.spinner("냉장고에 넣는 중..."):
                        for item, put, expiry in rows:
                            if not put:
                                continue  # 체크를 푼 재료는 넣지 않고 목록에서만 뺀다.
                            name, unit = item["name"], item["unit"]
                            # 같은 이름이 다른 단위로만 있으면 따로 줄이 생긴다는 걸 알려 주기 위해 미리 확인
                            if fridge_store.find_all_by_name(fridge_items, name) and not fridge_store.find_in_fridge_by_name(
                                fridge_items, name, unit=unit
                            ):
                                separate.append(name)
                            fridge_store.add_item(
                                fridge_items, name, expiry, float(item["quantity"]), unit,
                                known_info(name), allow_new_unit=True,
                            )
                    shop.remove_items(data, [item["id"] for item in bought])

                    finish(True, f"{', '.join(separate)}은(는) 단위가 달라서 따로 넣었어요." if separate else "")



    # ---------------------------------------------------------------
    # [＋ 직접 추가] 팝업: 머리 영역의 버튼으로 연다. 열린 상태를 shop_add_open에 기억해 둔다.
    # ---------------------------------------------------------------
    def close_shop_add():
        st.session_state.shop_add_open = False


    @st.dialog("🛒 장바구니에 직접 추가", on_dismiss=close_shop_add)
    def shop_add_dialog():
        """이름을 입력하고 Enter를 누르면 추천 단위를 채워 준다. (냉장고 추가와 같은 방식)"""
        SHOP_ADD_DEFAULTS = {
            "shop_name": "", "shop_quantity": 1.0, "shop_unit": classifier.DEFAULT_UNIT,
            "shop_units": classifier.common_units(None),  # 고를 수 있는 단위 (재료 종류에 흔한 단위만)
        }
        for k, v in SHOP_ADD_DEFAULTS.items():
            st.session_state.setdefault(k, v)


        def on_shop_name_change():
            """이름이 바뀌면 추천 단위를 채우고, 고를 수 있는 단위를 그 재료에 흔한 단위로 줄인다."""
            state = st.session_state
            name = state.shop_name.strip()
            if not name:
                state.shop_units = classifier.common_units(None)
                return
            with st.spinner(f"'{name}' 단위 추천 중..."):
                info = known_info(name)
            state.shop_units = classifier.common_units(info["category"], info["unit"])
            state.shop_unit = info["unit"]


        def on_shop_add_click():
            """[담기] 버튼: 직접 입력한 항목을 장보기 리스트에 담는다."""
            state = st.session_state
            name = state.shop_name.strip()
            if not name:
                state.shop_add_msg = "재료 이름을 입력해 주세요."
                return
            ok, message = shop.add_item(data, name, state.shop_quantity, state.shop_unit, shop.SOURCE_MANUAL)
            if not ok:
                state.shop_add_msg = message  # 팝업 안에 보여 준다. (이미 있음 등)
                return
            for k, v in SHOP_ADD_DEFAULTS.items():
                state[k] = v
            state.shop_add_open = False  # 담았으면 팝업을 닫는다. (목록에 보이므로 알림 없음)


        if "shop_add_msg" in st.session_state:
            st.warning(st.session_state.pop("shop_add_msg"))
        # 두 줄로: [이름] / [수량] [단위] [담기]
        with st.container():
            st.text_input("이름", key="shop_name", on_change=on_shop_name_change, placeholder="예: 두부")
            col_qty, col_unit, col_btn = st.columns([1.3, 1.2, 1], vertical_alignment="bottom")
            col_qty.number_input("수량", min_value=0.1, step=1.0, format="%g", key="shop_quantity")
            if st.session_state.shop_unit not in st.session_state.shop_units:
                st.session_state.shop_unit = st.session_state.shop_units[0]
            col_unit.selectbox("단위", st.session_state.shop_units, key="shop_unit")
            col_btn.button("담기", key="shop_add", type="primary", on_click=on_shop_add_click, width="stretch")
        if not st.session_state.shop_add_open:
            st.rerun()  # 담았으면 팝업을 닫고 장바구니를 새로 그린다.
        ui.save_draft("shop_add")  # 새로고침해도 적던 내용이 남게


    if st.session_state.get("shop_add_open"):
        shop_add_dialog()


