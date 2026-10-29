"""OpenRouter AI 호출 공통 모듈 (재료 분류·요리 추천이 함께 쓴다)

무료 모델은 사용자가 몰리면 잠깐씩 막힌다(429 오류).
그래서 첫 번째 모델이 막히면 다음 모델로 다시 시도하도록 여러 개를 적어 둔다.
"""

import base64
import json
import os
import re
import time

import requests
from dotenv import load_dotenv

# .env 파일의 키들을 환경 변수로 읽어 온다. (내 컴퓨터에서 실행할 때)
load_dotenv()

# Gemma가 막히는 일이 많아서, 응답이 잘 오는 NVIDIA Nemotron 무료 모델을 뒤에 둔다.
AI_MODELS = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-26b-a4b-it:free",
]
# 사진(영수증)을 읽을 수 있는 무료 모델. 위 목록과 같은 방식으로 앞에서부터 시도한다.
VISION_MODELS = [
    "nvidia/nemotron-3.5-super-vl:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
]
VISION_TIMEOUT = 45         # 초. 사진은 글보다 오래 걸려서 넉넉하게
VISION_TOTAL_TIMEOUT = 90   # 초
AI_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_TIMEOUT = 20        # 초. 모델 하나가 이 시간 안에 답이 없으면 다음 모델로
AI_TOTAL_TIMEOUT = 40  # 초. 모든 모델을 합쳐 이 시간이 지나면 실패로 처리 (너무 오래 기다리지 않게)


def get_secret(name):
    """키를 찾는다. 내 컴퓨터에서는 .env, Streamlit Cloud에서는 Secrets 설정에서 읽는다."""
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st

        return st.secrets.get(name)
    except Exception:
        # Secrets 설정이 아예 없으면 오류가 나므로 조용히 None을 돌려준다.
        return None


def ask_json(prompt, validate=lambda data: data, total_timeout=AI_TOTAL_TIMEOUT):
    """AI에게 묻고, 답에서 JSON 부분을 꺼내 validate로 확인한 결과를 돌려준다. 실패하면 None.

    validate: JSON을 받아 쓸 수 있는 값으로 바꿔 주는 함수. 쓸 수 없는 답이면 None을 돌려준다.
    모델을 앞에서부터 차례로 시도하고, 처음으로 쓸 수 있게 답한 결과를 쓴다.
    전체 시간(total_timeout)을 넘기면 남은 모델은 건너뛴다.
    """
    return _ask_models(AI_MODELS, prompt, validate, AI_TIMEOUT, total_timeout)


def ask_json_with_image(prompt, image_bytes, mime="image/jpeg", validate=lambda data: data):
    """사진과 함께 묻는다. (영수증 읽기) 사용법은 ask_json과 같다.

    사진은 base64 글자로 바꿔서 "data:image/jpeg;base64,..." 형태로 보낸다.
    """
    encoded = base64.b64encode(image_bytes).decode("ascii")
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
    ]
    return _ask_models(VISION_MODELS, content, validate, VISION_TIMEOUT, VISION_TOTAL_TIMEOUT)


def _ask_models(models, content, validate, timeout, total_timeout):
    """모델 목록을 앞에서부터 시도해서, 처음으로 validate를 통과한 결과를 돌려준다."""
    api_key = get_secret("OPENROUTER_API_KEY")
    if not api_key:
        return None
    deadline = time.monotonic() + total_timeout
    for model in models:
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            break
        data = _ask_one_model(api_key, model, content, timeout=min(timeout, remaining))
        result = validate(data) if data is not None else None
        if result:
            return result
    return None


def _ask_one_model(api_key, model, prompt, timeout):
    """모델 하나에 요청해서 답의 JSON을 돌려준다. 실패하면 None.

    prompt: 글자(str), 또는 글자+사진을 담은 목록(list)
    """
    try:
        response = requests.post(
            AI_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                # 답하기 전 '생각하는 단계'를 끈다. 켜 두면 Nemotron은 같은 답에 2분 넘게 걸린다(꺼면 몇 초).
                "reasoning": {"enabled": False},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError):
        # 인터넷 문제, 무료 모델 호출 한도 초과(429), 이상한 응답 등은 모두 실패로 처리
        return None

    # AI가 ```json ... ``` 처럼 감싸서 답해도 { } 또는 [ ] 부분만 꺼내서 읽는다.
    found = re.search(r"[\[{].*[\]}]", text or "", re.DOTALL)
    if not found:
        return None
    try:
        return json.loads(found.group())
    except json.JSONDecodeError:
        return None
