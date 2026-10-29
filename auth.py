"""로그인 화면과 로그인 유지 (5단계: 사용자별 개인 냉장고)

- 로그인하지 않았으면 닉네임·비밀번호 화면(로그인 / 처음이에요)을 보여 주고 앱을 멈춘다.
- 로그인하면 st.session_state["user"]에 닉네임을 넣는다. → storage.py가 이 사람 데이터만 읽고 쓴다.
- 새로고침하면 Streamlit의 화면 기억(session_state)이 비므로, 로그인할 때 받은 토큰을
  브라우저 저장소(localStorage)에 넣어 두고, 다음에 열 때 그 토큰으로 자동 로그인한다.
  (토큰 원문은 브라우저에만, 저장소에는 토큰의 해시만 있다)
"""

import streamlit as st

import storage

state = st.session_state
STORE_KEY = "ft_login"  # 브라우저 저장소에 쓰는 이름

# 보이지 않는 작은 컴포넌트: 토큰을 저장/삭제하고, 처음 한 번 저장된 토큰을 Python에 알려 준다.
_JS = """
export default function (component) {
    const { data, setStateValue } = component;
    try {
        if (data.save) localStorage.setItem("%s", data.save);
        if (data.clear) localStorage.removeItem("%s");
        if (!data.checked) setStateValue("token", localStorage.getItem("%s") || "");
    } catch (e) {
        if (!data.checked) setStateValue("token", "");  // 저장소를 못 쓰는 브라우저면 그냥 로그인 화면
    }
}
""" % (STORE_KEY, STORE_KEY, STORE_KEY)

_keeper = st.components.v2.component("auth_keeper", js=_JS)


def _on_token():
    """브라우저에서 토큰이 오면 그 토큰의 닉네임으로 로그인한다."""
    token = (state.get("auth_keeper") or {}).get("token") or ""
    state.auth_checked = True
    try:
        nickname = storage.user_from_token(token)
    except storage.StorageError:
        nickname = None
    if nickname:
        state.user = nickname
        state.auth_token = token


def _keep():
    _keeper(
        key="auth_keeper",
        data={"checked": bool(state.get("auth_checked")), "save": state.pop("auth_save", None),
              "clear": state.pop("auth_clear", False)},
        on_token_change=_on_token,
    )


def _log_in(nickname):
    state.user = nickname
    state.auth_token = storage.new_token(nickname)
    state.auth_save = state.auth_token  # 다음 실행에서 브라우저 저장소에 넣는다.
    st.rerun()


def _login_form():
    st.title("🧊 스마트 냉장고")
    st.caption("내 냉장고를 쓰려면 닉네임으로 로그인하세요.")
    tab_in, tab_new = st.tabs(["로그인", "처음이에요"])
    with tab_in, st.form("login_form"):
        nickname = st.text_input("닉네임")
        password = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인", type="primary", width="stretch"):
            try:
                ok, message = storage.sign_in(nickname, password)
            except storage.StorageError as error:
                ok, message = False, str(error)
            if ok:
                _log_in(nickname.strip())
            st.error(message)
    with tab_new, st.form("signup_form"):
        nickname = st.text_input("닉네임", help="2~20자 한글·영문·숫자")
        password = st.text_input("비밀번호", type="password", help=f"{storage.MIN_PASSWORD}자 이상")
        again = st.text_input("비밀번호 확인", type="password")
        if st.form_submit_button("계정 만들기", type="primary", width="stretch"):
            if password != again:
                st.error("비밀번호 확인이 맞지 않아요.")
            else:
                try:
                    ok, message = storage.sign_up(nickname, password)
                except storage.StorageError as error:
                    ok, message = False, str(error)
                if ok:
                    _log_in(nickname.strip())
                st.error(message)


def require_login():
    """로그인했으면 닉네임을 돌려주고, 아니면 로그인 화면을 보여 주고 여기서 멈춘다."""
    _keep()
    if state.get("user"):
        return state.user
    # shortcut: 새로고침 직후 토큰을 확인하기 전 잠깐 로그인 화면이 보인다. 거슬리면 확인 중 화면을 따로 둘 것
    _login_form()
    st.stop()


def log_out():
    """로그아웃: 토큰을 지우고 화면 기억도 비운다. (브라우저 저장소의 토큰은 다음 실행에서 지운다)"""
    try:
        storage.drop_token(state.get("auth_token"))
    except storage.StorageError:
        pass  # 저장소에 못 지워도 브라우저에서는 지우므로 자동 로그인은 되지 않는다.
    for key in list(state.keys()):
        del state[key]
    state.auth_checked = True
    state.auth_clear = True


def keep_keys():
    """화면 상태를 모두 지울 때(테스트 데이터 넣기 등) 남겨야 하는 로그인 정보"""
    return {key: state[key] for key in ("user", "auth_token", "auth_checked") if key in state}
