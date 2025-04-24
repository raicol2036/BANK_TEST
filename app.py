# golf_bet_app/app.py
# 高爾夫對賭最終版（點數 × 人數 × 單局賭金 - 已確認洞 × 單局賭金）

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

st.set_page_config(page_title="高爾夫對賭", layout="wide")

st.title("🏌️ 高爾夫對賭賽事系統")

course_db = {
    "台中國際(東區)": {"par": [4, 4, 3, 5, 4, 4, 3, 5, 4], "handicap": [2, 8, 5, 4, 7, 1, 9, 3, 6]},
    "台中國際(西區)": {"par": [5, 4, 3, 4, 4, 3, 4, 5, 4], "handicap": [3, 6, 9, 8, 1, 4, 7, 2, 5]},
    "台中國際(中區)": {"par": [4, 4, 3, 5, 4, 4, 3, 4, 5], "handicap": [7, 2, 8, 5, 4, 1, 9, 3, 6]}
}

if "players" not in st.session_state:
    st.session_state.players = ["Lee", "Joye", "Raicol", "Jerry"]
if "confirmed" not in st.session_state:
    st.session_state.confirmed = set()

st.header("球場設定")
front = st.selectbox("前九洞球場", list(course_db.keys()), key="front")
back = st.selectbox("後九洞球場", list(course_db.keys()), key="back")
par = course_db[front]["par"] + course_db[back]["par"]
hcp = course_db[front]["handicap"] + course_db[back]["handicap"]

players = st.multiselect("選擇參賽球員", st.session_state.players, default=st.session_state.players[:4])
new = st.text_input("新增球員")
if new and new not in st.session_state.players:
    st.session_state.players.append(new)
    players.append(new)

handicaps = {p: st.number_input(f"{p} 差點", 0, 54, 0, key=f"hcp_{p}") for p in players}
bet_per_person = st.number_input("單局賭金（每人）", 10, 1000, 100)

scores = pd.DataFrame(index=players, columns=[f"第{i+1}洞" for i in range(18)])
events = pd.DataFrame(index=players, columns=[f"第{i+1}洞" for i in range(18)])

st.header("輸入每洞成績")
event_opts = ["none", "sand", "water", "ob", "miss", "3putt"]

for i in range(18):
    st.subheader(f"第{i+1}洞 (Par {par[i]} / HCP {hcp[i]})")
    cols = st.columns(len(players))
    for j, p in enumerate(players):
        with cols[j]:
            scores.loc[p, f"第{i+1}洞"] = st.number_input(f"{p} 桿數", 1, 15, par[i], key=f"score_{p}_{i}")
            events.loc[p, f"第{i+1}洞"] = ",".join(st.multiselect(f"{p} 事件", event_opts, default=["none"], key=f"event_{p}_{i}"))

    confirmed = st.checkbox(f"✅ 確認第{i+1}洞成績", key=f"confirm_{i}")
    if confirmed:
        st.session_state.confirmed.add(i)
        st.success(f"✅ 第{i+1}洞成績已確認")
    else:
        st.warning(f"⚠️ 第{i+1}洞尚未確認，將不納入點數計算")

if st.button("🔍 計算總結果"):
    adjust = scores.copy()
    for i in range(18):
        for p in players:
            let = 0  # 讓桿邏輯可補上
            adjust.loc[p, f"第{i+1}洞"] -= let

    point_bank = 1
    points = {p: 0 for p in players}
    titles = {p: None for p in players}
    log = []

    for i in range(18):
        if i not in st.session_state.confirmed:
            continue

        col = f"第{i+1}洞"
        raw = scores[col]
        adj = adjust[col]
        evts = events[col]

        min_score = adj.min()
        winners = adj[adj == min_score].index.tolist()

        penalties = {p: 0 for p in players}
        for p in players:
            e = evts[p].split(",")
            raw_score = raw[p]
            title = "SuperRich" if points[p] >= 8 else "Rich" if points[p] >= 4 else None
            if title:
                pen = 0
                if raw_score >= par[i] + 3 or "3putt" in e:
                    pen += 1
                if any(x in e for x in ["sand", "water", "ob"]):
                    pen += 1
                if title == "SuperRich" and "miss" in e:
                    pen += 1
                pen = min(pen, 3)
                points[p] -= pen
                penalties[p] = pen
        point_bank += sum(penalties.values())

        if len(winners) == 1:
            w = winners[0]
            transfer = 0
            if raw[w] <= par[i] - 1:
                for p in players:
                    if p != w and points[p] > 0:
                        points[p] -= 1
                        transfer += 1
            actual_bonus = point_bank + transfer
            points[w] += actual_bonus
            log.append(f"第{i+1}洞 勝者: {w} 🎯 +{actual_bonus} 點")
            point_bank = 1
        else:
            log.append(f"第{i+1}洞 平手，銀行累積中：{point_bank} 點")

    completed_holes = len(st.session_state.confirmed)
    total_bet = bet_per_person * len(players)
    result = pd.DataFrame({
        "總點數": [points[p] for p in players],
        "賭金結果": [points[p] * total_bet - completed_holes * bet_per_person for p in players],
        "頭銜": ["SuperRich" if points[p] >= 8 else "Rich" if points[p] >= 4 else "" for p in players]
    }, index=players).sort_values("賭金結果", ascending=False)

    st.header("比賽結果總表")
    st.dataframe(result.style.applymap(lambda v: "background-color: gold" if v == "SuperRich" else "background-color: lightblue" if v == "Rich" else "", subset=["頭銜"]))

    st.subheader("洞別說明 Log")
    for line in log:
        st.text(line)
