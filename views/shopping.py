"""🛒 장보기 (사이드바 메뉴)

장보기 화면은 냉장고 화면 위에 겹친 "닫힌 냉장고 문"이다. (views/fridge.py + shopping_panel.py)
이 메뉴를 누르면 문을 닫은 상태로 냉장고 화면으로 보낸다.
"""

import streamlit as st

st.session_state.home_view = "door"
st.switch_page("views/fridge.py")
