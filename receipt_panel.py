"""🧾 영수증 등록 팝업 (2단계)

냉장고·장보기 화면의 [🧾 영수증] 버튼을 누르면 뜨는 팝업. (views/fridge.py에서 연다)
1) 영수증 사진을 찍거나(휴대폰) 올리고 [영수증 읽기] → AI가 가게·날짜·식재료(이름·수량·단위·가격)를 읽는다.
2) 표에서 확인·수정한다. (유통기한은 종류별 보통 기한으로 미리 채워 두니 포장 날짜로 고친다)
3) [냉장고에 넣기] → 냉장고에 넣고, 장바구니에 같은 재료가 있으면 장바구니에서 뺀다.
   (가게·날짜·가격은 지금은 저장하지 않는다. 3단계 구매 기록에서 쓸 예정)

사진은 읽을 때만 쓰고 저장하지 않는다.
"""

from datetime import date

import pandas as pd
import streamlit as st

import classifier
import fridge_store
import receipt_reader
import shopping_store as shop
import ui

state = st.session_state
TAKE, PICK = "📷 사진 찍기", "🖼️ 사진 올리기"


def open_receipt():
    """[🧾 영수증] 버튼: 팝업을 처음 상태(사진 올리기)로 연다."""
    state.receipt_rows = None
    state.receipt_open = True


def close_receipt():
    """팝업의 ✕를 누르면 닫는다."""
    state.receipt_open = False


def make_rows(result):
    """AI 결과를 표의 줄로 바꾼다. 유통기한은 종류별 보통 기한으로 미리 채운다."""
    bought = date.fromisoformat(result["date"]) if result.get("date") else date.today()
    rows = []
    for item in result["items"]:
        info = classifier.classify_quick(item["name"]) or {}
        item = receipt_reader.fix_unit(item, info)  # '두부 300g' → '두부 1모'
        rows.append(
            {
                "넣기": True,
                "이름": item["name"],
                "수량": item["quantity"],
                "단위": item["unit"],
                "가격": item["price"],
                "유통기한": receipt_reader.guess_expiry(info.get("category"), info.get("storage"), bought),
            }
        )
    return rows


def show_result(result, store_name="", bought=None):
    """표를 새로 채운다."""
    state.receipt_rows = make_rows(result) if result else []
    state.receipt_store = store_name
    state.receipt_date = bought or date.today()
    state.receipt_ver += 1


def clean(value):
    """표의 빈 칸(NaN·NaT)을 None으로 바꾼다."""
    return None if pd.isna(value) else value


@st.dialog("🧾 영수증 등록", width="large", on_dismiss=close_receipt)
def receipt_dialog():
    state.setdefault("receipt_rows", None)  # 읽은 결과 (표에 보여 줄 줄들). None이면 아직 안 읽음
    state.setdefault("receipt_ver", 0)      # 표를 새로 채울 때 바꿔서 이전 수정 내용을 지운다.
    # ---------------------------------------------------------------
    # 1) 사진 올리기 → 읽기
    # ---------------------------------------------------------------
    if state.receipt_rows is None:
        state.pop("receipt_draft", None)  # 표가 없으면 임시 저장한 표도 지운다.
        # [📷 사진 찍기]로 카메라(PC는 웹캠)를 켜거나, [🖼️ 사진 올리기]로 파일·앨범에서 고른다.
        # 처음 고른 쪽: 휴대폰은 찍기, PC는 올리기. (카메라는 https 주소에서만 켜진다. 배포 사이트·localhost는 괜찮다)
        how = st.segmented_control(
            "사진 고르는 방법", [TAKE, PICK], default=TAKE if ui.is_mobile() else PICK, required=True,
            key="receipt_how", label_visibility="collapsed", width="stretch",
        )
        if how == TAKE:
            # 글자가 잘 읽히도록 높은 해상도로 찍는다.
            photo = st.camera_input("영수증 찍기", key="receipt_cam", label_visibility="collapsed",
                                    resolution="1080p")
        else:
            photo = st.file_uploader(
                "영수증 사진", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed",
            )
        col_read, col_manual, _ = st.columns([1, 1, 2])
        if col_read.button("영수증 읽기", type="primary", disabled=photo is None, width="stretch"):
            with st.spinner("영수증을 읽는 중... (1분 정도 걸릴 수 있어요)"):
                result = receipt_reader.read_receipt(photo.getvalue(), photo.type or "image/jpeg")
            if result and result["items"]:
                bought = date.fromisoformat(result["date"]) if result["date"] else None
                show_result(result, result["store"], bought)
                st.rerun()  # 다시 그려도 팝업은 열린 채로(receipt_open) 표가 보인다.
            st.warning("영수증을 읽지 못했어요. 사진을 밝고 반듯하게 다시 찍거나, 직접 입력해 주세요.")
        if col_manual.button("직접 입력", width="stretch"):
            show_result({"items": [], "date": None})
            st.rerun()
        if photo is not None and how == PICK:
            st.image(photo, width=260)  # (찍은 사진은 카메라 칸에 이미 보인다)
        return


    # ---------------------------------------------------------------
    # 2) 확인·수정 표
    # ---------------------------------------------------------------
    # shortcut: 가게·산 날짜 입력칸은 저장할 곳(3단계 구매 기록)이 생기면 다시 보여 준다.
    st.caption("유통기한은 보통 기한으로 채워 두었어요. 포장에 적힌 날짜로 고쳐 주세요. 비우면 '기한 없음'이에요.")
    table = pd.DataFrame(
        state.receipt_rows, columns=["넣기", "이름", "수량", "단위", "가격", "유통기한"]
    )
    edited = st.data_editor(
        table,
        key=f"receipt_editor_{state.receipt_ver}",
        num_rows="dynamic",  # 표 아래에서 줄을 더하거나 지울 수 있다.
        hide_index=True,
        width="stretch",
        column_config={
            "넣기": st.column_config.CheckboxColumn(width="small", default=True),
            "이름": st.column_config.TextColumn(required=True),
            "수량": st.column_config.NumberColumn(min_value=0.1, step=1, format="%g", default=1),
            "단위": st.column_config.SelectboxColumn(options=fridge_store.UNITS, default="개", required=True),
            "가격": st.column_config.NumberColumn("가격(원)", min_value=0, step=10, format="%,d"),
            "유통기한": st.column_config.DateColumn(format="YYYY-MM-DD"),
        },
    )

    # 새로고침해도 고친 표가 남게 임시 저장한다. (빈 칸은 None, 날짜는 날짜로)
    state.receipt_draft = [
        {k: (v.date() if isinstance(v, pd.Timestamp) else clean(v)) for k, v in row.items()}
        for row in edited.to_dict("records")
    ]
    ui.save_draft("receipt")

    rows = [
        row for row in edited.to_dict("records")
        if row.get("넣기") and isinstance(row.get("이름"), str) and row["이름"].strip()
    ]


    col_put, col_reset, _ = st.columns([1.4, 1, 1.6])
    put_clicked = col_put.button(f"냉장고에 넣기 ({len(rows)})", type="primary", disabled=not rows, width="stretch")
    if col_reset.button("다시 올리기", width="stretch"):
        state.receipt_rows = None
        st.rerun()

    if put_clicked:
        fridge_items = fridge_store.load_items()
        cart = shop.load()
        names = []
        with st.spinner("냉장고에 넣는 중..."):
            for row in rows:
                name = row["이름"].strip()
                quantity = float(clean(row["수량"]) or 1)
                unit = clean(row["단위"]) or "개"
                expiry = clean(row["유통기한"])
                if expiry is not None and not isinstance(expiry, date):
                    expiry = pd.Timestamp(expiry).date()
                fridge_store.add_item(
                    fridge_items, name, expiry, quantity, unit, classifier.classify(name), allow_new_unit=True
                )
                names.append(name)
            # 장바구니에 같은 재료가 있으면 산 것이니 뺀다.
            in_cart = [shop.find_by_name(cart, name) for name in names]
            in_cart = [item for item in in_cart if item]
            shop.remove_items(cart, [item["id"] for item in in_cart])

        state.receipt_rows = None
        state.receipt_open = False
        if in_cart:  # 넣은 재료는 새 재료 봉투에 보이므로, 안 보이는 장바구니 쪽만 알린다.
            state.flash = (True, f"장바구니에서도 뺐어요: {', '.join(item['name'] for item in in_cart)}")
        st.rerun()  # 팝업을 닫고 냉장고 화면을 새로 그린다.
