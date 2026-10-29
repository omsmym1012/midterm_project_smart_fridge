"""사용자별 데이터 저장과 계정 (5단계: 사용자별 개인 냉장고)

- 로그인한 사람(st.session_state["user"] = 닉네임)마다 냉장고·장보기·사용 기록을 따로 저장한다.
- 저장 위치
  1) Supabase(무료 온라인 DB): .env 또는 Streamlit Secrets에 SUPABASE_URL, SUPABASE_KEY가 있을 때.
     다시 배포해도 데이터가 남는다. 키는 service_role 키를 서버에서만 쓰고 브라우저로 보내지 않는다.
  2) 키가 없으면 내 컴퓨터의 data/users/<닉네임>/<이름>.json 파일 (.gitignore의 data/라 커밋되지 않음)
- 로그인하지 않은 상태(테스트 스크립트 등)에서는 각 모듈의 원래 파일(DATA_FILE)을 그대로 쓴다.

[Supabase 테이블] (SQL은 CLAUDE.md의 5단계 설명 참고)
    app_users(nickname 기본키, pw_hash)
    user_data(nickname, name, data jsonb)   -- name: "fridge" / "shopping" / "usage_log"
    login_tokens(token_hash 기본키, nickname)  -- 새로고침해도 로그인 유지용
"""

import copy
import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path

import requests

from ai_client import get_secret

ROOT = Path(__file__).parent / "data" / "users"
NICK_RULE = re.compile(r"^[0-9A-Za-z가-힣_-]{2,20}$")  # 폴더 이름으로도 쓰므로 글자를 제한한다.
MIN_PASSWORD = 4


class StorageError(Exception):
    """저장소(Supabase)에 연결하지 못했을 때. 빈 데이터로 덮어쓰지 않도록 조용히 넘기지 않는다."""


def current_user():
    """지금 로그인한 닉네임 (없으면 None)"""
    try:
        import streamlit as st

        return st.session_state.get("user")
    except Exception:
        return None


# ---------------------------------------------------------------
# 파일 / Supabase 공통 읽기·쓰기
# ---------------------------------------------------------------
def _read_file(path, default):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _write_file(path, data):
    """임시 파일에 쓴 뒤 바꿔치기 (저장 도중 꺼져도 파일이 망가지지 않게)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _supabase():
    url, key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
    return (url.rstrip("/"), key) if url and key else None


def _rest(method, table, params=None, body=None, prefer=None):
    """Supabase REST(PostgREST) 호출. 실패하면 StorageError."""
    url, key = _supabase()
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # 예전 방식 service_role 키(JWT)만 Authorization에도 넣는다. 새 sb_secret_ 키는 apikey만
        headers["Authorization"] = f"Bearer {key}"
    if prefer:
        headers["Prefer"] = prefer
    try:
        response = requests.request(method, f"{url}/rest/v1/{table}", params=params, json=body,
                                    headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        raise StorageError(f"저장소에 연결하지 못했어요. 잠시 후 다시 시도해 주세요. ({error})") from error
    return response.json() if response.text else None


# Supabase에서 읽은 데이터를 서버 메모리에 기억해 둔다. (화면을 그릴 때마다 여러 번 인터넷으로 읽으면 느려서)
# 저장도 이 서버를 거치므로 저장할 때 같이 바꿔 두면 항상 최신이다.
# shortcut: 서버가 하나일 때만 맞다(Streamlit Cloud 기본). 서버를 여러 대 띄우면 이 기억을 없앨 것
_cache = {}


def load(name, fallback_file, default):
    """이 사용자의 데이터 하나를 읽는다. name: "fridge" 등, fallback_file: 로그인 전(테스트)에 쓰는 파일"""
    user = current_user()
    if user is None:
        return _read_file(fallback_file, default)
    if _supabase():
        if (user, name) not in _cache:
            rows = _rest("GET", "user_data", {"nickname": f"eq.{user}", "name": f"eq.{name}", "select": "data"})
            _cache[(user, name)] = rows[0]["data"] if rows else default
        return copy.deepcopy(_cache[(user, name)])  # 받은 쪽이 고쳐도 기억해 둔 값은 그대로
    return _read_file(ROOT / user / f"{name}.json", default)


def save(name, fallback_file, data):
    """이 사용자의 데이터 하나를 저장한다. (있으면 바꾸고 없으면 새로)"""
    user = current_user()
    if user is None:
        _write_file(fallback_file, data)
    elif _supabase():
        _rest("POST", "user_data", body={"nickname": user, "name": name, "data": data},
              prefer="resolution=merge-duplicates")
        _cache[(user, name)] = copy.deepcopy(data)  # 저장에 성공했을 때만 기억도 바꾼다.
    else:
        _write_file(ROOT / user / f"{name}.json", data)


# ---------------------------------------------------------------
# 계정: 회원가입 / 로그인 / 로그인 유지 토큰
# 비밀번호는 그대로 저장하지 않고 소금(salt)을 섞은 해시(PBKDF2)로만 저장한다.
# ---------------------------------------------------------------
def _hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${digest}"


def _check_password(password, stored):
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(_hash_password(password, salt), stored)


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _get_pw_hash(nickname):
    if _supabase():
        rows = _rest("GET", "app_users", {"nickname": f"eq.{nickname}", "select": "pw_hash"})
        return rows[0]["pw_hash"] if rows else None
    return _read_file(ROOT / "_accounts.json", {}).get(nickname)


def sign_up(nickname, password):
    """새 계정을 만든다. 반환: (성공 여부, 메시지)"""
    nickname = nickname.strip()
    if not NICK_RULE.match(nickname):
        return False, "닉네임은 2~20자의 한글·영문·숫자·_·-만 쓸 수 있어요."
    if len(password) < MIN_PASSWORD:
        return False, f"비밀번호는 {MIN_PASSWORD}자 이상으로 정해 주세요."
    if _get_pw_hash(nickname):
        return False, "이미 있는 닉네임이에요. 다른 닉네임을 쓰거나 로그인해 주세요."
    pw_hash = _hash_password(password)
    if _supabase():
        _rest("POST", "app_users", body={"nickname": nickname, "pw_hash": pw_hash})
    else:
        accounts = _read_file(ROOT / "_accounts.json", {})
        accounts[nickname] = pw_hash
        _write_file(ROOT / "_accounts.json", accounts)
    return True, f"'{nickname}' 계정을 만들었어요."


def sign_in(nickname, password):
    """닉네임·비밀번호가 맞는지. 반환: (성공 여부, 메시지)"""
    stored = _get_pw_hash(nickname.strip())
    if not stored or not _check_password(password, stored):
        return False, "닉네임이나 비밀번호가 맞지 않아요."
    return True, ""


def new_token(nickname):
    """로그인 유지 토큰을 만든다. 브라우저에는 토큰을, 저장소에는 토큰의 해시만 둔다."""
    token = secrets.token_urlsafe(32)
    if _supabase():
        _rest("POST", "login_tokens", body={"token_hash": _token_hash(token), "nickname": nickname})
    else:
        tokens = _read_file(ROOT / "_tokens.json", {})
        tokens[_token_hash(token)] = nickname
        _write_file(ROOT / "_tokens.json", tokens)
    return token


def user_from_token(token):
    """브라우저에 저장된 토큰으로 닉네임을 찾는다. 없거나 틀리면 None"""
    if not token:
        return None
    if _supabase():
        rows = _rest("GET", "login_tokens", {"token_hash": f"eq.{_token_hash(token)}", "select": "nickname"})
        return rows[0]["nickname"] if rows else None
    return _read_file(ROOT / "_tokens.json", {}).get(_token_hash(token))


def drop_token(token):
    """로그아웃: 이 토큰으로는 다시 자동 로그인되지 않게 지운다."""
    if not token:
        return
    if _supabase():
        _rest("DELETE", "login_tokens", {"token_hash": f"eq.{_token_hash(token)}"})
    else:
        tokens = _read_file(ROOT / "_tokens.json", {})
        tokens.pop(_token_hash(token), None)
        _write_file(ROOT / "_tokens.json", tokens)


if __name__ == "__main__":
    # 자체 확인 (파일 방식): 가입 → 로그인 → 토큰 → 사용자별로 따로 저장
    import tempfile
    from unittest import mock

    ROOT = Path(tempfile.mkdtemp())
    with mock.patch(__name__ + "._supabase", return_value=None):
        assert sign_up("민지", "1234")[0] and not sign_up("민지", "5678")[0] and not sign_up("a", "1234")[0]
        assert sign_in("민지", "1234")[0] and not sign_in("민지", "0000")[0]
        token = new_token("민지")
        assert user_from_token(token) == "민지"
        drop_token(token)
        assert user_from_token(token) is None
        for nick, value in (("민지", [1]), ("준호", [2])):
            with mock.patch(__name__ + ".current_user", return_value=nick):
                save("fridge", None, value)
        with mock.patch(__name__ + ".current_user", return_value="민지"):
            assert load("fridge", None, []) == [1]
    print("ok")
