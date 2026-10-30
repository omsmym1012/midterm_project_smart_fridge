"""🍳 요리 추천 페이지 (탭 2개)

1) 재료로 찾기: 쓰고 싶은 재료를 고르고(처음에는 유통기한 3일 이내 재료) [추천 받기]를 누르면 요리 3개를 보여 준다.
   - 식품안전나라 레시피에서 먼저 고르고, 모자라면 AI로 채운다. (recipe_store.recommend)
2) 요리로 찾기: 만들고 싶은 요리를 레시피 목록에서 검색해 고르면, 냉장고에 있는 재료와 부족한 재료를 보여 준다.
두 탭 모두 부족한 재료는 골라서 장바구니에 담을 수 있다.
"""

import streamlit as st

import classifier
import fridge_store
import recipe_store
import shopping_panel
import shopping_store as shop
import ui
from fridge_board import fridge_board

st.title("🍳 요리 추천")
state = st.session_state

items = fridge_store.load_items()
fridge = recipe_store.usable_items(items)

# [장바구니로 가기]: 알림은 한 번만 보여서 다음 실행엔 버튼이 없으므로, 누를 때 콜백으로 표시해 두고 여기서 옮긴다.
if state.pop("recipe_go_cart", False):
    state.goto_tab = shopping_panel.TAB_CART
    st.switch_page("views/fridge.py", query_params={"show": "door"})

if "flash" in st.session_state:
    ok, message = st.session_state.pop("flash")
    if ok:
        # 초록 알림 줄: 왼쪽 메시지, 오른쪽 끝 [장바구니로 가기]
        st.html("""<style>.st-key-recipe_flash { background: rgba(33, 195, 84, 0.12); border-radius: 0.5rem;
            padding: 0.6rem 0.6rem 0.6rem 1rem; } .st-key-recipe_flash p { margin: 0; }
            .st-key-recipe_to_cart { margin-left: auto; }  /* 줄이 바뀌어도 오른쪽 끝 */</style>""")
        with st.container(key="recipe_flash", horizontal=True, vertical_alignment="center"):
            st.markdown(f":green[{message}]", width="stretch")
            st.button("🛒 장바구니로 가기", key="recipe_to_cart", on_click=lambda: state.update(recipe_go_cart=True))
    else:
        st.warning(message)

def add_missing(names, dish, listed=()):
    """고른 부족한 재료를 장보기 리스트에 담는다. 장바구니에서 요리(dish)별로 묶여 보인다.

    listed: 이 요리에 필요한데 이미 장바구니에 있는 재료. 담지는 않고 '이 요리에도 써요' 표시만 더한다.
    """
    data = shop.load()
    for name in listed:
        shop.add_item(data, name, 1.0, "", shop.SOURCE_RECIPE, dish=dish)  # 이미 있어서 요리 이름만 더해진다.
    added, skipped = [], []
    with st.spinner("장바구니에 담는 중..."):
        for name in names:
            unit = classifier.classify(name)["unit"]  # 재료에 맞는 단위 (목록·캐시·AI)
            ok, _ = shop.add_item(data, name, 1.0, unit, shop.SOURCE_RECIPE, dish=dish)
            (added if ok else skipped).append(name)
    message = f"🛒 장바구니에 담았어요: {', '.join(added)}" if added else ""
    if skipped:
        message += f" (이미 있음: {', '.join(skipped)})"
    state.flash = (bool(added), message.strip())
    st.rerun()


def render_card(index, pick):
    recipe = pick["recipe"]
    with st.container(border=True):
        col_img, col_info = st.columns([1, 2])
        if recipe["image"]:
            col_img.image(recipe["image"], width="stretch")
        else:
            col_img.markdown("### 🍳")

        with col_info:
            badge = " :violet-badge[AI 추천]" if pick["source"] == "ai" else ""
            st.markdown(f"#### {recipe['name']}{badge}")
            info = " · ".join(x for x in [recipe["kind"], recipe["way"], f"{recipe['kcal']}kcal" if recipe["kcal"] else ""] if x)
            if info:
                st.caption(info)
            if pick["source"] == "ai" and recipe["tip"]:
                st.caption(recipe["tip"])

            # 쓰는 냉장고 재료 (임박 재료는 주황색 배지)
            # 쓰고 싶은 재료로 고른 것은 주황색 배지로 강조한다.
            uses = [f":orange-badge[{n}]" if n in pick["picked"] else n for n in pick["uses"]]
            uses += [f":gray[{n}]" for n in pick["basic"]]  # 냉장고에 있는 기본 양념은 회색으로 뒤에
            st.markdown(f"**냉장고 재료:** {', '.join(uses) or '없음'}")

            listed = [m for m in pick["missing"] if shop.find_by_name(shop.load(), m)]
            to_buy = [m for m in pick["missing"] if m not in listed]
            if not pick["missing"]:
                st.markdown("**부족한 재료:** 없음")
            else:
                st.markdown(f"**부족한 재료:** {', '.join(pick['missing'])}")
                if to_buy:
                    # 여러 줄로 감기는 버튼 목록이라 재료가 많아도 잘리지 않는다. 누르면 고르기/풀기.
                    chosen = st.pills(
                        "장바구니에 담을 재료", to_buy, selection_mode="multi", default=to_buy, wrap=True, width="stretch",
                        key=f"recipe_missing_{index}_{recipe['name']}", label_visibility="collapsed",
                    ) or []
                    if st.button("장바구니에 담기", key=f"recipe_add_{index}_{recipe['name']}", disabled=not chosen):
                        add_missing(chosen, recipe["name"], listed)
                else:
                    st.caption("🛒 모두 장바구니에 있어요.")

        with st.expander("조리 순서"):
            for step in recipe["steps"]:
                st.markdown(step if step[:1].isdigit() else f"- {step}")
            if not recipe["steps"]:
                st.caption("조리 순서가 없는 레시피예요. 재료만 참고해 주세요.")
            if pick["source"] == "api":
                if recipe["parts"]:
                    st.caption(f"재료 전체: {recipe['parts']}")
                if recipe["tip"]:
                    st.caption(f"💡 {recipe['tip']}")
                st.caption(f"출처: {recipe_store.source_name(recipe)}")


# ---------------------------------------------------------------
# 탭 2개: 재료로 찾기 / 요리로 찾기
# ---------------------------------------------------------------
tab_ing, tab_dish = st.tabs(["🥕 재료로 찾기", "🍲 요리로 찾기"], key="recipe_tab", on_change="rerun")  # 고른 탭을 기억(다른 페이지에 다녀와도)

with tab_ing:
    if not fridge:
        st.info("요리에 쓸 재료가 없어요. 냉장고에 재료를 먼저 추가해 주세요.")
    else:
        # 추천 결과는 화면이 다시 그려져도 유지되도록 session_state에 둔다.

        # 쓰고 싶은 재료 고르기: 처음에는 유통기한 3일 이내 재료가 골라져 있다.
        names = [f["name"] for f in fridge]
        dday = {f["name"]: f["dday"] for f in fridge}
        soon_names = [f["name"] for f in fridge if f["soon"]]
        if "recipe_board_done" in state:
            # 팝업에서 [고르기 완료]로 고른 목록을 고르기 칸을 그리기 전에 넣는다.
            state.recipe_chosen = state.pop("recipe_board_done")
        if "recipe_chosen" in state:
            # 냉장고에서 빠진 재료는 선택에서도 뺀다. (없는 선택지가 남아 있으면 오류가 난다)
            state.recipe_chosen = [n for n in state.recipe_chosen if n in names]
        else:
            state.recipe_chosen = soon_names
        # 고른 재료 태그를 모두 같은 너비로 (글자 길이에 따라 들쭉날쭉하지 않게, 넘치는 글자는 …)
        tag_width = "calc(50% - 0.3rem)" if ui.is_mobile() else "9.5rem"  # 휴대폰은 한 줄에 2개
        st.html(f"""<style>
            .st-key-recipe_chosen span[data-tag] {{ width: {tag_width}; justify-content: space-between; }}
            .st-key-recipe_chosen span[data-tag] > span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        </style>""")
        st.multiselect(
            "쓰고 싶은 재료",
            names,
            key="recipe_chosen",
            format_func=lambda n: f"{'🟠 ' if n in soon_names else ''}{n} ({dday[n]})",
            placeholder="쓰고 싶은 재료를 골라 주세요",
        )

        # [🧊 냉장고에서 고르기]: 냉장고 그림 팝업에서 재료를 눌러 고른다.
        # 팝업은 따로 다시 그려지므로 고르기 칸(recipe_chosen)을 바로 바꾸면 화면의 옛 값에 덮인다.
        # 그래서 팝업에서는 recipe_board_sel에 고르고, [고르기 완료]를 누를 때 고르기 칸에 넣는다.
        def open_board():
            state.recipe_board_sel = list(state.recipe_chosen)
            state.recipe_board_open = True


        def on_board_toggle():
            item_id = (state.get("recipe_board") or {}).get("toggle")
            name = next((i["name"] for i in items if i["id"] == item_id), None)
            if name in names:
                sel = state.recipe_board_sel
                state.recipe_board_sel = [n for n in sel if n != name] if name in sel else sel + [name]


        @st.dialog("🧊 냉장고에서 고르기", width="large", on_dismiss=lambda: state.update(recipe_board_open=False))
        def board_dialog():
            st.caption("쓰고 싶은 재료를 누르세요. 다시 누르면 풀려요. (기한 지난 재료는 보이지 않아요)")
            fridge_board(
                [i for i in items if i["name"] in names], key="recipe_board", on_move=lambda: None,
                on_toggle=on_board_toggle, mobile=ui.is_mobile(), pick_only=True,
                selected=[i["id"] for i in items if i["name"] in state.recipe_board_sel],
            )
            if st.button(f"고르기 완료 ({len(state.recipe_board_sel)})", type="primary", width="stretch",
                         key="recipe_board_ok"):
                state.recipe_board_done = state.recipe_board_sel
                state.recipe_board_open = False
                st.rerun()


        st.button("🧊 냉장고에서 고르기", on_click=open_board)
        if state.get("recipe_board_open"):
            board_dialog()
        state.setdefault("recipe_picks", None)
        state.setdefault("recipe_notice", None)
        state.setdefault("recipe_seen_ids", [])     # 이미 보여 준 레시피 (다른 요리 보기에서 제외)
        state.setdefault("recipe_seen_names", [])


        def run_recommend(more=False):
            """추천을 받아 session_state에 넣는다. more=True면 이미 본 요리는 빼고 새로 고른다."""
            if not more:
                state.recipe_seen_ids, state.recipe_seen_names = [], []
            with st.spinner("요리를 찾는 중... (처음에는 레시피를 받느라 조금 걸려요)"):
                picks, notice = recipe_store.recommend(
                    items, state.recipe_chosen, state.recipe_seen_ids, state.recipe_seen_names
                )
            state.recipe_picks, state.recipe_notice = picks, notice
            state.recipe_seen_ids += [p["recipe"]["id"] for p in picks if p["recipe"]["id"]]
            state.recipe_seen_names += [p["recipe"]["name"] for p in picks]


        col_new, col_more, _ = st.columns([1, 1.3, 2])
        # 쓰고 싶은 재료를 하나도 고르지 않으면 추천 버튼을 누를 수 없다. (냉장고 전체로 추천하지 않음)
        nothing = not state.recipe_chosen
        if col_new.button("추천 받기", type="primary", disabled=nothing):
            run_recommend()
        if state.recipe_picks and col_more.button("다른 요리 보기", disabled=nothing):
            run_recommend(more=True)

        if state.recipe_notice:
            st.warning(f"{state.recipe_notice} AI 추천만 보여 줘요.")

        if state.recipe_picks is not None and not state.recipe_picks:
            st.warning("추천할 요리를 찾지 못했어요. 잠시 후 다시 시도해 주세요.")


        for i, pick in enumerate(state.recipe_picks or []):
            render_card(i, pick)


with tab_dish:
    # 만들고 싶은 요리를 골라 부족한 재료 보기 (레시피 목록에서만 고른다)
    try:
        with st.spinner("레시피 목록을 불러오는 중... (처음에는 조금 걸려요)"):
            recipes = recipe_store.load_recipes()
    except recipe_store.RecipeError as error:
        recipes = []
        st.warning(f"레시피 목록을 불러오지 못했어요. {error}")
    if recipes:
        by_id = {r["id"]: r for r in recipes}
        ordered = sorted(by_id, key=lambda i: (len(by_id[i]["name"]), by_id[i]["name"]))
        def dish_label(i):
            return by_id[i]["name"] if i in by_id else i  # 목록에 없는 글자를 직접 친 경우는 그 글자

        dish_id = st.selectbox(
            # 이름이 짧은 요리 먼저: '된장찌개'를 찾으면 그냥 된장찌개가 '냉이된장찌개'보다 위에 온다.
            "만들고 싶은 요리", ordered, index=None, format_func=dish_label,
            placeholder="요리 이름을 검색해 보세요 (예: 된장찌개)", key="dish_pick",
            # 검색칸은 띄어쓰기까지 똑같아야 찾는다. 못 찾으면 친 글자 그대로 고를 수 있게 하고(Add: …) 아래에서 다시 찾는다.
            accept_new_options=True,
        )
        if dish_id and dish_id not in by_id:
            # 띄어쓰기를 빼고 다시 찾는다. 똑같은 이름 → 이름에 들어 있는 것 중 가장 짧은 이름
            typed = dish_id.replace(" ", "")
            found = [i for i in ordered if typed in by_id[i]["name"].replace(" ", "")]
            exact = [i for i in found if by_id[i]["name"].replace(" ", "") == typed]
            dish_id = (exact or found or [None])[0]
            if not dish_id:
                st.info(f"'{typed}' 레시피가 없어요. 다른 이름으로 찾아보세요.")
        if dish_id:
            # 냉장고 재료와 비교해서 있는 재료 / 부족한 재료 / 기본 양념으로 나눈다.
            pick = recipe_store.score_recipe(by_id[dish_id], fridge)
            render_card("dish", pick)
