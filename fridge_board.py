"""냉장고 칸 모양 화면 (드래그 앤 드롭 컴포넌트)

Streamlit 기본 위젯에는 드래그 앤 드롭이 없어서, st.components.v2로
HTML·CSS·JavaScript를 직접 넣은 작은 컴포넌트를 만든다.

- 왼쪽: 실제 냉장고처럼 그린 그림 (금속 몸체, 조명이 켜진 안쪽, 유리 선반, 신선칸 서랍, 열린 문의 문칸 바구니)
  위에서부터 냉동실 → 냉장실, 그 아래 냉장고 밖(조리대)
- 오른쪽 옆(휴대폰은 맨 아래): 아직 칸에 넣지 않은 "새 재료" (장바구니 봉투 모양, 폭 TRAY_WIDTH)
- 냉장고 몸체는 화면 폭 전체, 높이는 FRIDGE_HEIGHT (장보기의 닫힌 문과 같은 크기)
- 다른 페이지에서 넘어오면 문이 열리는 효과, 다크 모드면 어두운 색 (ui.py가 붙인 html[data-ft])
- 재료를 마우스(또는 손가락)로 잡으면 추천 칸 색이 연하게 바뀌고,
  다른 칸에 놓으면 Python으로 {"item_id", "zone"}을 보낸다. ("move" 이벤트)
- 끌지 않고 누르기만 하면 그 재료를 고르거나 푼다. ("toggle" 이벤트, 고른 재료는 파란 테두리)
"""

import streamlit as st

import classifier
import fridge_store as store

# 컴포넌트 모양
CSS = """
/* ---------- 색 (밝은 테마 / 다크 모드) ---------- */
.fb-root {
    --fb-body: linear-gradient(140deg, #fbfcfd 0%, #e9eef2 60%, #dbe2e8 100%);  /* 냉장고 겉면 */
    --fb-edge: #DCE3E8;
    --fb-inside: #ffffff;                                                    /* 냉장실 안 */
    --fb-frost: linear-gradient(180deg, #f7fbfe 0%, #edf4f9 100%);           /* 냉동실 안 (살짝 차갑게) */
    --fb-sub: #5B6775;                                                       /* 칸 이름 등 보조 글자 */
    --fb-primary: #2456C8;                                                   /* 고른 재료 표시 */
    --fb-light: rgba(255, 244, 214, 0.75);                                  /* 안쪽 조명 */
    --fb-glass: rgba(140, 185, 210, 0.55);                                  /* 유리 선반·바구니 */
    --fb-handle: linear-gradient(90deg, #aab5bb, #e9eef0, #9aa6ac);
    --fb-chip: #ffffff;
    --fb-line: #DCE3E8;
    --fb-counter: linear-gradient(180deg, #e2c49c 0%, #cfa977 100%);        /* 조리대(냉장고 밖) */
    --fb-counter-text: #4b3722;
    --fb-bag: linear-gradient(180deg, #ecd9b6 0%, #e0c899 100%);            /* 장바구니 봉투(새 재료) */
    --fb-bag-text: #5a4429;
    --fb-shadow: 0 10px 24px rgba(30, 45, 50, 0.18);
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 12px;
    color: var(--st-text-color, inherit);
    font-family: var(--st-font, inherit);
    user-select: none;
    -webkit-user-select: none;
}
.fb-root.fb-dark {
    --fb-body: linear-gradient(140deg, #3a444d 0%, #2c343c 60%, #232a31 100%);
    --fb-edge: #2A333D;
    --fb-inside: #1f2a33;
    --fb-frost: linear-gradient(180deg, #213040 0%, #1d2a36 100%);
    --fb-sub: #93A0AE;
    --fb-primary: #6E9BFF;
    --fb-light: rgba(255, 236, 190, 0.18);
    --fb-glass: rgba(120, 175, 205, 0.45);
    --fb-handle: linear-gradient(90deg, #5d6a71, #9aa7ad, #4f5a60);
    --fb-chip: #1C232B;
    --fb-line: #2A333D;
    --fb-counter: linear-gradient(180deg, #6b5136 0%, #574129 100%);
    --fb-counter-text: #f3e4cf;
    --fb-bag: linear-gradient(180deg, #6e5a3c 0%, #5c4a30 100%);
    --fb-bag-text: #f5e8d2;
    --fb-shadow: 0 10px 24px rgba(0, 0, 0, 0.45);
}

/* ---------- 냉장고 몸체 ---------- */
.fb-fridge {
    min-height: var(--fb-height);   /* 장보기 페이지의 닫힌 문과 같은 높이 (FRIDGE_HEIGHT) */
    box-sizing: border-box;
    display: flex; flex-direction: column; gap: 6px;
    padding: 10px 10px 4px;
    background: var(--fb-body);
    border: 1px solid var(--fb-edge);
    border-radius: 14px;
    box-shadow: var(--fb-shadow), inset 0 1px 0 rgba(255, 255, 255, 0.5);
    perspective: 1400px;
    position: relative;
}
.fb-section { position: relative; display: flex; flex-direction: column; }
.fb-fridge-part { flex: 1; }
.fb-fridge-part .fb-cavity { flex: 1; }
.fb-fridge-part .fb-shelves .fb-zone { flex: 1 0 auto; }   /* 남는 높이는 나눠 갖되, 재료보다 작아지지는 않게 */
.fb-section-title {
    font-weight: 700; font-size: 0.78rem; letter-spacing: 0.02em;
    padding: 0 4px 4px; opacity: 0.75;
}
/* 안쪽 공간: 왼쪽 선반들 + 오른쪽 문칸(열린 문) */
.fb-cavity {
    display: grid; grid-template-columns: 1fr 34%; gap: 8px;
}
.fb-shelves {
    position: relative;   /* 넘쳐도 자르지 않는다 (재료가 많으면 칸이 길어진다) */
    display: flex; flex-direction: column;
    background: var(--fb-inside);
    border-radius: 8px;
    padding: 6px 8px 8px;
    box-shadow: inset 0 3px 10px rgba(0, 0, 0, 0.12), inset 0 0 0 1px rgba(0, 0, 0, 0.06);
}
.fb-freezer .fb-shelves { background: var(--fb-frost); }
/* 안쪽 위의 조명 */
.fb-shelves::before {
    content: ""; position: absolute; left: 15%; right: 15%; top: 0; height: 40px; border-radius: 8px 8px 0 0;
    background: radial-gradient(ellipse at center, var(--fb-light), transparent 70%);
    pointer-events: none;
}

/* ---------- 칸 ---------- */
.fb-zone {
    position: relative;
    padding: 4px 4px 6px;
    min-height: 54px;
    border-radius: 6px;
    transition: background-color 0.15s, outline-color 0.15s;
    outline: 2px solid transparent; outline-offset: -2px;
}
/* 선반: 아래에 유리판 */
.fb-shelf { border-bottom: 5px solid var(--fb-glass); border-radius: 6px 6px 2px 2px; margin-bottom: 4px; }
.fb-shelf::after {
    content: ""; position: absolute; left: 0; right: 0; bottom: -5px; height: 2px;
    background: rgba(255, 255, 255, 0.55);
}
/* 신선칸: 반투명 서랍 + 손잡이 홈 */
.fb-drawer {
    margin-top: 2px;
    background: color-mix(in srgb, var(--fb-glass) 22%, transparent);
    border: 2px solid var(--fb-glass);
    border-radius: 10px;
    padding-top: 12px;
}
.fb-drawer::before {
    content: ""; position: absolute; left: 50%; top: 4px; width: 46px; height: 4px; margin-left: -23px;
    border-radius: 4px; background: var(--fb-glass);
}
/* 문칸: 열린 문 안쪽 + 바구니들 */
.fb-door {
    position: relative;
    background: var(--fb-body);
    border-radius: 8px;
    border: 3px solid color-mix(in srgb, var(--fb-edge) 70%, transparent);
    padding: 8px 8px 8px;
    box-shadow: inset 4px 0 8px rgba(0, 0, 0, 0.08);
}
.fb-door .fb-zone {
    min-height: 100%; box-sizing: border-box;
    border: 2px solid var(--fb-glass); border-top-width: 0;
    border-radius: 0 0 10px 10px;
    background: color-mix(in srgb, var(--fb-glass) 20%, transparent);
}
.fb-door::after {   /* 문 손잡이 */
    content: ""; position: absolute; right: -8px; top: 26%; width: 11px; height: 48%;
    border-radius: 6px; background: var(--fb-handle);
    border: 1px solid var(--fb-edge); box-shadow: 2px 3px 6px rgba(0, 0, 0, 0.3);
}
/* 냉장실 문 손잡이: 누르면 문이 닫힌다(장보기). 그림 손잡이(::after) 대신 진짜 요소 */
.fb-fridge-part .fb-door::after { display: none; }
.fb-grip {
    position: absolute; right: -9px; top: 26%; width: 13px; height: 48%; z-index: 3;
    border-radius: 7px; background: var(--fb-handle);
    border: 1px solid var(--fb-edge); box-shadow: 2px 3px 6px rgba(0, 0, 0, 0.3);
    cursor: pointer;
}
.fb-grip:hover { filter: brightness(1.1); }

/* 다리 */
.fb-feet { display: flex; justify-content: space-between; padding: 0 26px; height: 6px; }
.fb-feet span { width: 26px; height: 6px; border-radius: 0 0 6px 6px; background: var(--fb-edge); }

/* 냉장고 밖: 조리대 */
.fb-counter {
    margin-top: 6px; border-radius: 10px; padding: 6px 8px 8px;
    background: var(--fb-counter); box-shadow: var(--fb-shadow);
}
.fb-counter .fb-zone-title { color: var(--fb-counter-text); opacity: 0.9; }

/* 새 재료: 장바구니 봉투 */
.fb-tray {
    background: var(--fb-bag); border-radius: 6px 6px 14px 14px;
    padding: 14px 8px 10px; box-shadow: var(--fb-shadow);
    border-top: 2px dashed rgba(90, 68, 41, 0.35);
}
.fb-tray .fb-zone-title { color: var(--fb-bag-text); opacity: 0.95; font-weight: 700; }
/* 봉투 안의 [추천 칸에 모두 넣기] / [완료] 버튼 */
.fb-tray-btn {
    display: block; width: 100%; margin: 2px 0 8px; padding: 7px 8px; box-sizing: border-box;
    font: inherit; font-size: 0.85rem; font-weight: 700; cursor: pointer;
    border: none; border-radius: 8px; background: var(--fb-primary); color: #fff;
}
.fb-dark .fb-tray-btn { color: #0d1420; }
.fb-tray-btns { display: flex; gap: 6px; }
.fb-tray-btn.fb-secondary { background: var(--fb-chip); color: var(--st-text-color, inherit); border: 1px solid var(--fb-line); }
.fb-tray-btn:focus-visible { outline: 2px solid var(--fb-bag-text); outline-offset: 2px; }
.fb-new-bar { font-size: 0.82rem; font-weight: 700; color: var(--fb-bag-text); margin-bottom: 4px; }
/* 자동으로 넣은 재료: 노란 형광펜 ([완료]를 누르면 사라진다) */
.fb-chip.fb-new { background: color-mix(in srgb, #FFD43B 30%, var(--fb-chip)); }

.fb-zone-title { font-size: 0.75rem; color: var(--fb-sub); margin-bottom: 6px; cursor: pointer; user-select: none; }
.fb-list { display: flex; flex-direction: column; gap: 5px; min-height: 26px; }
.fb-list:empty::after { content: attr(data-empty); font-size: 0.72rem; opacity: 0.55; }

/* ---------- 재료 카드: 왼쪽 굵은 선 색 = 유통기한 상태 ---------- */
.fb-chip {
    display: flex; justify-content: space-between; align-items: center; gap: 8px;
    padding: 6px 8px;
    border-radius: 6px;
    background: var(--fb-chip);
    border: 1px solid var(--fb-line);
    border-left: 4px solid var(--fb-status);
    color: var(--st-text-color, inherit);
    cursor: pointer; touch-action: none;
    font-size: 0.9rem; line-height: 1.3;
}
.fb-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fb-meta {
    flex: none; font-size: 0.82rem; font-weight: 700; color: var(--fb-status);
    font-variant-numeric: tabular-nums;
}
.fb-expired { --fb-status: #D9363E; }
.fb-soon { --fb-status: #E89A1C; }
.fb-ok { --fb-status: #2F9E66; }
.fb-none { --fb-status: #8B96A3; }

/* 추천 칸 (재료를 짚었을 때) / 지금 놓으려는 칸 */
.fb-zone.fb-recommend { background: rgba(47, 158, 102, 0.14); outline-color: #2F9E66; outline-style: dashed; }
.fb-zone.fb-over { background: color-mix(in srgb, var(--fb-primary) 16%, transparent); outline-color: var(--fb-primary); }

/* 끌고 다니는 카드와, 원래 자리에 남는 흐린 카드 */
.fb-ghost {
    position: absolute; z-index: 10; pointer-events: none; opacity: 0.92;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25); cursor: grabbing;
}
.fb-placeholder { opacity: 0.35; }

/* 고른 재료는 파란 테두리와 ✓ 표시 */
.fb-chip.fb-selected { outline: 2px solid var(--fb-primary); outline-offset: 0; }
.fb-chip.fb-selected .fb-name::before { content: "✓ "; color: var(--fb-primary); font-weight: 700; }

/* ---------- 문 열림 효과 (다른 페이지에서 넘어왔을 때만) ---------- */
.fb-panel {
    position: absolute; inset: 0; z-index: 5;
    background: var(--fb-body);
    border: 1px solid var(--fb-edge); border-radius: 14px;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
    transform-origin: left center;
    animation: fb-open 0.9s cubic-bezier(0.55, 0.05, 0.35, 1) forwards;
    pointer-events: none;
}
.fb-panel::after {   /* 닫힌 문의 손잡이 */
    content: ""; position: absolute; right: 14px; top: 18%; width: 11px; height: 64%;
    border-radius: 6px; background: var(--fb-handle); box-shadow: 2px 3px 6px rgba(0, 0, 0, 0.3);
}
.fb-fridge-part .fb-panel { animation-delay: 0.12s; }
@keyframes fb-open {
    0%   { transform: rotateY(0deg); opacity: 1; }
    80%  { opacity: 1; }
    100% { transform: rotateY(-105deg); opacity: 0; visibility: hidden; }
}

/* ---------- 휴대폰 화면 ---------- */
.fb-root:not(.fb-mobile) { flex-direction: row; align-items: flex-start; }
.fb-root:not(.fb-mobile) .fb-left { flex: 1; min-width: 0; }
.fb-root:not(.fb-mobile) .fb-tray { flex: none; width: var(--fb-tray-width); box-sizing: border-box; }
.fb-root.fb-mobile { gap: 10px; }
.fb-mobile .fb-tray { padding-top: 10px; }
.fb-mobile .fb-fridge { padding: 8px 8px 4px; }
.fb-mobile .fb-cavity { grid-template-columns: 1fr 38%; gap: 6px; }
.fb-mobile .fb-chip { font-size: 0.8rem; padding: 5px 6px; }
.fb-mobile .fb-meta { font-size: 0.74rem; }
"""

# 냉장고 몸체 높이(px). 장보기 페이지의 닫힌 문도 이 값을 써서 두 화면의 냉장고 크기를 똑같이 맞춘다.
FRIDGE_HEIGHT = 640
FRIDGE_HEIGHT_MOBILE = 560
# PC에서 냉장고 오른쪽 옆 "새 재료" 봉투의 폭(px)과 사이 간격. 장보기 문은 이만큼 오른쪽을 비워서 냉장고 몸체에만 겹친다.
TRAY_WIDTH = 190
TRAY_GAP = 12

# 컴포넌트 동작
# 재료 이름은 사용자가 입력한 글자이므로 innerHTML이 아니라 textContent로만 넣는다. (스크립트 실행 방지)
JS = """
export default function (component) {
    const { data, parentElement, setTriggerValue } = component;

    // 화면이 다시 그려질 때마다 이전 내용을 지우고 새로 만든다.
    const old = parentElement.querySelector(".fb-root");
    if (old) old.remove();
    const root = document.createElement("div");
    root.className = "fb-root";
    parentElement.appendChild(root);

    const titles = data.zones;      // 칸 id → 칸 이름
    const selected = new Set(data.selected || []);  // 골라 둔 재료 id들
    const lists = {};               // 칸 id → 재료 카드가 들어가는 영역
    const zoneBoxes = [];           // 재료를 놓을 수 있는 칸들 ("새 재료" 포함)
    let dragging = null;            // 지금 끌고 있는 재료 정보

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function makeZone(id, title, extraClass) {
        const box = el("div", "fb-zone " + (extraClass || ""));
        box.dataset.zone = id;
        const list = el("div", "fb-list");
        const head = el("div", "fb-zone-title", title);
        if (id !== "tray" && !data.pickOnly) {
            // 칸 이름을 더블클릭하면 봉투의 재료 중 이 칸이 추천 칸인 것만 넣는다.
            head.title = "더블클릭: 이 칸이 추천 칸인 새 재료 넣기";
            head.addEventListener("dblclick", () => setTriggerValue("fill", { zone: id, at: Date.now() }));
        }
        box.append(head, list);
        lists[id] = list;
        zoneBoxes.push(box);
        return box;
    }

    // 냉장실 / 냉동실: 왼쪽은 선반들(맨 아래 신선칸은 서랍), 오른쪽은 열린 문의 문칸
    function makeSection(title, shelfIds, doorId, partClass) {
        const section = el("div", "fb-section " + partClass);
        const cavity = el("div", "fb-cavity");
        const shelves = el("div", "fb-shelves");
        shelfIds.forEach((id) => shelves.appendChild(makeZone(id, titles[id], id === "crisper" ? "fb-drawer" : "fb-shelf")));
        const door = el("div", "fb-door");
        door.appendChild(makeZone(doorId, titles[doorId]));
        if (partClass === "fb-fridge-part" && !data.pickOnly) {
            // 손잡이를 누르면 Python에 알려서 문을 닫는다. (장보기 화면)
            const grip = el("div", "fb-grip");
            grip.title = "문 닫기 (장보기)";
            grip.addEventListener("click", () => setTriggerValue("close", Date.now()));
            door.appendChild(grip);
        }
        cavity.append(shelves, door);
        section.append(el("div", "fb-section-title", title), cavity);
        // 다른 페이지에서 넘어왔으면 닫힌 문을 덮어 두었다가 열리는 효과를 보여 준다.
        if (data.animate) section.appendChild(el("div", "fb-panel"));
        return section;
    }

    // 테마(밝게/어둡게)와 휴대폰 화면 표시
    function applyTheme() {
        root.classList.toggle("fb-dark", document.documentElement.dataset.ft === "dark");
    }
    applyTheme();
    // 이전 그림에서 만든 감시는 끊고 새로 단다. (다시 그릴 때마다 쌓이지 않게)
    if (window.__fbThemeWatch) window.__fbThemeWatch.disconnect();
    window.__fbThemeWatch = new MutationObserver(applyTheme);
    window.__fbThemeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-ft"] });
    if (data.mobile) root.classList.add("fb-mobile");

    const fridge = el("div", "fb-fridge");
    // 위에서부터 냉동실 → 냉장실 (일반 가정용 냉장고처럼 냉동실이 위) + 다리
    const feet = el("div", "fb-feet");
    feet.append(el("span"), el("span"));
    fridge.append(
        makeSection("❄️ 냉동실", ["freezer"], "freezer_door", "fb-freezer"),
        makeSection("🧊 냉장실", ["top", "middle", "bottom", "crisper"], "door", "fb-fridge-part"),
        feet
    );
    // 냉장고 밖은 조리대 모양으로 냉장고 아래에
    const left = el("div", "fb-left");
    left.append(fridge, makeZone("outside", "🍳 " + titles.outside + " (실온)", "fb-counter"));
    // 냉장고 문이 닫혀 있을 때(장보기 화면)는 냉장고 밖(조리대)을 감춘다.
    if (data.hideOutside) left.lastChild.style.display = "none";
    root.style.setProperty("--fb-height", data.height + "px");
    root.style.setProperty("--fb-tray-width", data.trayWidth + "px");
    root.style.gap = data.mobile ? "10px" : data.trayGap + "px";
    const tray = makeZone("tray", "🛍️ 새 재료", "fb-tray");
    lists.tray.dataset.empty = "새 재료가 없어요";
    root.append(left, tray);

    // 봉투에 재료가 있으면 [추천 칸에 모두 넣기], 자동으로 넣은 재료가 있으면 "새로 넣은 재료 N개 [완료]"
    const newIds = new Set(data.newIds || []);
    const inTray = data.items.filter((item) => !(item.zone && lists[item.zone])).length;
    function trayButton(text, trigger, extraClass) {
        const btn = el("button", "fb-tray-btn " + (extraClass || ""), text);
        btn.type = "button";
        btn.addEventListener("click", () => setTriggerValue(trigger, Date.now()));
        return btn;
    }
    if (newIds.size && !data.pickOnly) {
        tray.insertBefore(el("div", "fb-new-bar", "새로 넣은 재료 " + newIds.size + "개"), lists.tray);
        // [완료]: 표시만 지우기 / [취소]: 방금 넣은 재료를 다시 봉투로
        const row = el("div", "fb-tray-btns");
        row.append(trayButton("완료", "done"), trayButton("취소", "undo", "fb-secondary"));
        tray.insertBefore(row, lists.tray);
    }
    if (inTray && !data.pickOnly) tray.insertBefore(trayButton("추천 칸에 모두 넣기", "autoplace"), lists.tray);

    function setRecommend(zoneId, on) {
        zoneBoxes.forEach((box) => box.classList.toggle("fb-recommend", on && box.dataset.zone === zoneId));
    }

    // 손가락/마우스 위치에 있는 칸 찾기
    function zoneAt(x, y) {
        return zoneBoxes.find((box) => {
            const r = box.getBoundingClientRect();
            return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
        });
    }


    function makeChip(item) {
        const chip = el("div", "fb-chip fb-" + item.status);
        chip.dataset.id = item.id;
        if (selected.has(item.id)) chip.classList.add("fb-selected");
        if (newIds.has(item.id)) chip.classList.add("fb-new");
        chip.append(el("span", "fb-name", item.name), el("span", "fb-meta", item.meta));
        chip.title = "추천 칸: " + titles[item.recommend];

        chip.addEventListener("pointerenter", () => { if (!dragging) setRecommend(item.recommend, true); });
        chip.addEventListener("pointerleave", () => { if (!dragging) setRecommend(item.recommend, false); });
        chip.addEventListener("pointerdown", (event) => startDrag(event, chip, item));
        // 우클릭(마우스): 이 재료 하나만 사용하는 팝업. (휴대폰은 길게 누르기 → startDrag에서 처리)
        chip.addEventListener("contextmenu", (event) => {
            event.preventDefault();
            if (!data.pickOnly && lastPointer === "mouse") setTriggerValue("detail", item.id);
        });
        return chip;
    }

    let lastPointer = "mouse";  // 마지막으로 누른 것이 마우스인지 손가락인지 (우클릭 메뉴가 두 번 뜨지 않게)
    const LONG_PRESS = 500;     // ms. 손가락으로 이만큼 누르고 있으면 '길게 누르기'

    // 끌기: 포인터 이벤트를 써서 마우스와 터치에서 똑같이 동작하게 한다.
    function startDrag(event, chip, item) {
        lastPointer = event.pointerType;
        if (event.button !== 0) return;
        event.preventDefault();
        // 손가락으로 길게 누르면(움직이지 않고) 이 재료 하나만 사용하는 팝업을 연다. (휴대폰의 우클릭)
        let longPressed = false;
        const pressTimer = event.pointerType === "mouse" || data.pickOnly ? null : setTimeout(() => {
            if (ghost) return;
            longPressed = true;
            setTriggerValue("detail", item.id);
        }, LONG_PRESS);
        chip.setPointerCapture(event.pointerId);
        const rect = chip.getBoundingClientRect();
        const offsetX = event.clientX - rect.left;
        const offsetY = event.clientY - rect.top;
        const startX = event.clientX;
        const startY = event.clientY;
        let ghost = null;
        let over = null;
        dragging = item;
        setRecommend(item.recommend, true);

        function onMove(e) {
            // 조금이라도 움직였을 때부터 끌기로 본다. (그냥 누른 건 무시)
            if (!ghost) {
                if (data.pickOnly) return;  // 고르기 전용: 끌어도 옮기지 않고, 손을 떼면 누르기로 본다.
                if (Math.abs(e.clientX - startX) + Math.abs(e.clientY - startY) < 5) return;
                ghost = chip.cloneNode(true);
                ghost.classList.add("fb-ghost");
                ghost.style.width = rect.width + "px";
                root.appendChild(ghost);
                chip.classList.add("fb-placeholder");
            }
            const base = root.getBoundingClientRect();
            ghost.style.left = e.clientX - base.left - offsetX + "px";
            ghost.style.top = e.clientY - base.top - offsetY + "px";
            const target = zoneAt(e.clientX, e.clientY) || null;
            if (target !== over) {
                if (over) over.classList.remove("fb-over");
                if (target) target.classList.add("fb-over");
                over = target;
            }
        }

        function onEnd(e) {
            chip.removeEventListener("pointermove", onMove);
            chip.removeEventListener("pointerup", onEnd);
            chip.removeEventListener("pointercancel", onEnd);
            if (chip.hasPointerCapture(e.pointerId)) chip.releasePointerCapture(e.pointerId);
            if (over) over.classList.remove("fb-over");
            chip.classList.remove("fb-placeholder");
            setRecommend(item.recommend, false);
            dragging = null;
            clearTimeout(pressTimer);
            if (longPressed) return;  // 길게 누르기였으면 고르기/풀기는 하지 않는다.
            if (!ghost) {
                // 움직이지 않고 손을 뗐으면 "누르기": 고르기/풀기. 화면에서 먼저 바꿔 두고 Python에 알린다.
                if (e.type === "pointerup") {
                    chip.classList.toggle("fb-selected");
                    setTriggerValue("toggle", item.id);
                }
                return;
            }
            ghost.remove();

            const target = e.type === "pointerup" ? zoneAt(e.clientX, e.clientY) : null;
            if (!target) return;
            // 놓은 위치 바로 아래에 있는 카드 앞에 끼워 넣는다. (같은 칸이면 순서 바꾸기, 없으면 맨 끝)
            const list = lists[target.dataset.zone];
            const next = Array.from(list.children).find((c) => {
                if (!c.classList.contains("fb-chip") || c.dataset.id === item.id) return false;
                const r = c.getBoundingClientRect();
                return e.clientY < r.top + r.height / 2;
            }) || null;
            const nextSame = chip.nextElementSibling && chip.nextElementSibling.dataset.id !== item.id
                ? chip.nextElementSibling : null;
            if (chip.parentElement === list && next === nextSame) return;  // 제자리
            // 화면에서 먼저 옮겨 두고, Python에 알려서 저장한다.
            list.insertBefore(chip, next);
            const zone = target.dataset.zone === "tray" ? null : target.dataset.zone;
            setTriggerValue("move", { item_id: item.id, zone: zone, before: next ? next.dataset.id : null });
        }

        chip.addEventListener("pointermove", onMove);
        chip.addEventListener("pointerup", onEnd);
        chip.addEventListener("pointercancel", onEnd);
    }

    data.items.forEach((item) => {
        const zone = item.zone && lists[item.zone] ? item.zone : "tray";
        lists[zone].appendChild(makeChip(item));
    });
}
"""

# 컴포넌트 등록 (이 파일이 처음 import될 때 한 번만 실행된다)
_board = st.components.v2.component("fridge_board", css=CSS, js=JS)


def recommend(item, cache):
    """추천 칸: 이름으로 찾은 칸(목록·AI)을 먼저 쓰고, 없거나 보관 방법과 안 맞으면 종류 규칙을 쓴다."""
    zone = classifier.name_zone(item["name"], cache)
    if zone and store.zone_fits_storage(zone, item.get("storage")):
        return zone
    return store.recommend_zone(item)


def _board_data(items):
    """컴포넌트에 넘길 데이터: 칸 이름과 냉장고 재료 목록"""
    cache = classifier.load_cache()  # 재료마다 파일을 읽지 않도록 한 번만 읽는다.
    data_items = []
    for item in store.board_order(items):
        # 기한 지난 묶음과 남은 묶음이 섞여 있으면 카드를 두 장으로 나눠 보여 준다. (예: 우유 1팩 D+2 / 우유 1팩 D-5)
        # 두 카드는 같은 재료 id라서 고르기·옮기기·사용은 재료 단위로 함께 된다.
        expired = store.expired_batches(item)
        rest = [b for b in item["batches"] if b not in expired]
        parts = [expired, rest] if expired and rest else [item["batches"]]
        for batches in parts:
            first = store.earliest_batch({"batches": batches})
            data_items.append(
                {
                    "id": item["id"],
                    "name": f"{item['name']} {store.format_quantity(sum(b['quantity'] for b in batches), item['unit'])}",
                    "meta": store.d_day_label(first["expiry"]).replace(" 지남", ""),
                    "status": store.expiry_status(first["expiry"]),
                    "zone": item.get("zone"),
                    "recommend": recommend(item, cache),
                }
            )
    return {"zones": store.ZONES, "items": data_items}


def fridge_board(items, key, on_move, on_toggle, selected=(), animate=False, mobile=False, on_close=None,
                 hide_outside=False, new_ids=(), on_autoplace=None, on_done=None, on_undo=None,
                 on_fill=None, pick_only=False, on_detail=None):
    """냉장고 칸 화면을 그린다.

    재료를 다른 칸에 놓으면 on_move, 누르면 on_toggle이 화면을 다시 그리기 전에 먼저 실행된다.
    그 안에서 st.session_state[key]["move"]로 {"item_id", "zone", "before"(이 재료 앞에 끼움, 없으면 맨 끝)}을,
    st.session_state[key]["toggle"]로 누른(고르거나 푼) 재료 id를 읽을 수 있다.
    selected: 지금 골라 둔 재료 id들 (파란 테두리로 표시)
    animate=True: 문이 열리는 효과 (다른 페이지에서 넘어왔을 때)
    mobile=True: 휴대폰 화면 배치 (글씨 작게)
    on_close: 냉장실 문 손잡이를 눌렀을 때 실행 (문 닫기 → 장보기)
    hide_outside=True: 냉장고 밖(조리대)을 감춘다 (문이 닫힌 장보기 화면)
    new_ids: 자동으로 넣어서 노란 형광펜으로 표시할 재료 id들
    on_autoplace: 봉투의 [추천 칸에 모두 넣기]를 눌렀을 때, on_done: [완료], on_undo: [취소]를 눌렀을 때 실행
    on_fill: 칸 이름을 더블클릭했을 때 실행 (st.session_state[key]["fill"]["zone"]에 그 칸 id)
    on_detail: 재료를 우클릭(휴대폰은 길게 누르기)했을 때 실행 (st.session_state[key]["detail"]에 재료 id)
    pick_only=True: 누르기(고르기)만 된다. 끌어 옮기기·봉투 버튼·손잡이·칸 이름 더블클릭은 끈다. (요리 추천에서 재료 고르기)
    """
    data = _board_data(items)
    data["selected"] = list(selected)
    data["animate"] = animate
    data["mobile"] = mobile
    data["height"] = FRIDGE_HEIGHT_MOBILE if mobile else FRIDGE_HEIGHT
    data["trayWidth"] = TRAY_WIDTH
    data["trayGap"] = TRAY_GAP
    data["hideOutside"] = hide_outside
    data["newIds"] = list(new_ids)
    data["pickOnly"] = pick_only
    _board(
        data=data, key=key,
        on_move_change=on_move, on_toggle_change=on_toggle,
        on_close_change=on_close or (lambda: None),
        on_autoplace_change=on_autoplace or (lambda: None), on_done_change=on_done or (lambda: None),
        on_undo_change=on_undo or (lambda: None), on_fill_change=on_fill or (lambda: None),
        on_detail_change=on_detail or (lambda: None),
    )
