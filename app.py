# golf_bet_app/app.py — 修正最終 Rich/Super Rich 更新邏輯，避免語法錯誤

import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
from io import BytesIO

st.set_page_config(page_title="高爾夫對賭", layout="wide")

st.title("🏌️ 高爾夫對賭賽事系統")

course_db = {
    "台中國際(東區)": {"par": [4, 4, 3, 5, 4, 4, 3, 5, 4], "handicap": [2, 8, 5, 4, 7, 1, 9, 3, 6]},
    "台中國際(西區)": {"par": [5, 4, 3, 4, 4, 3, 4, 5, 4], "handicap": [3, 6, 9, 8, 1, 4, 7, 2, 5]},
    "台中國際(中區)": {"par": [4, 4, 3, 5, 4, 4, 3, 4, 5], "handicap": [7, 2, 8, 5, 4, 1, 9, 3, 6]}
}

CSV_PATH = "players.csv"
if "players" not in st.session_state:
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        st.session_state.players = df["name"].dropna().tolist()
    else:
        st.session_state.players = []
if "confirmed" not in st.session_state:
    st.session_state.confirmed = set()

st.header("球場設定")
front = st.selectbox("前九洞球場", list(course_db.keys()), key="front")
back = st.selectbox("後九洞球場", list(course_db.keys()), key="back")
par = course_db[front]["par"] + course_db[back]["par"]
hcp = course_db[front]["handicap"] + course_db[back]["handicap"]

players = st.multiselect("選擇參賽球員", st.session_state.players, default=[])
new = st.text_input("新增球員")
if new:
    if new not in st.session_state.players:
        st.session_state.players.append(new)
        st.success(f"✅ 已新增球員 {new} 至資料庫")
    if new not in players:
        players.append(new)

handicaps = {p: st.number_input(f"{p} 差點", 0, 54, 0, key=f"hcp_{p}") for p in players}

# 防呆：未選擇球員時不進入輸入區
if len(players) == 0:
    st.warning("⚠️ 請先選擇參賽球員")
    st.stop()
bet_per_person = st.number_input("單局賭金（每人）", 10, 1000, 100)

scores = pd.DataFrame(index=players, columns=[f"第{i+1}洞" for i in range(18)])
events = pd.DataFrame(index=players, columns=[f"第{i+1}洞" for i in range(18)])

st.header("輸入每洞成績")
# 讓桿計算準備
front_hcp = course_db[front]["handicap"]
back_hcp = course_db[back]["handicap"]

# 計算每位球員每區域需被讓幾桿（與最低差點者相比）
min_hcp = min(handicaps.values())
stroke_map = {
    p: {
        'front': sorted(front_hcp)[:max(0, handicaps[p] - min_hcp)],
        'back': sorted(back_hcp)[:max(0, handicaps[p] - min_hcp)]
    }
    for p in players
}

event_opts = ["none", "sand", "water", "ob", "miss", "3putt"]

running_points = {p: 0 for p in players}
current_titles = {p: "" for p in players}
log = []
point_bank = 1

for i in range(18):
    st.subheader(f"第{i+1}洞 (Par {par[i]} / HCP {hcp[i]})")
    cols = st.columns(len(players))
    for j, p in enumerate(players):
        with cols[j]:
            if current_titles[p] == "SuperRich":
                st.markdown("👑 **Super Rich Man**")
            elif current_titles[p] == "Rich":
                st.markdown("🏆 **Rich Man**")
            scores.loc[p, f"第{i+1}洞"] = st.number_input(f"{p} 桿數（{running_points[p]} 點）", 1, 15, par[i], key=f"score_{p}_{i}")
            events.loc[p, f"第{i+1}洞"] = ",".join(st.multiselect(f"{p} 事件", event_opts, default=["none"], key=f"event_{p}_{i}"))

    confirmed = st.checkbox(f"✅ 確認第{i+1}洞成績", key=f"confirm_{i}")
    if confirmed:
        st.session_state.confirmed.add(i)
        st.success(f"✅ 第{i+1}洞成績已確認")
    else:
        st.warning(f"⚠️ 第{i+1}洞尚未確認，將不納入點數計算")

    if confirmed:
        raw = scores[f"第{i+1}洞"]
        evt = events[f"第{i+1}洞"]
        # 計算讓桿後分數
adj = {}
for p in players:
    adj[p] = raw[p]
    if i < 9 and hcp[i] in stroke_map[p]['front']:
        adj[p] -= 1
    elif i >= 9 and hcp[i] in stroke_map[p]['back']:
        adj[p] -= 1

min_score = min(adj.values())
        winners = [p for p in players if adj[p] == min_score]
        penalties = {p: 0 for p in players}

        for p in players:
            acts = evt[p].split(",")
            title = current_titles[p]
            if title:
                pen = 0
                if raw[p] >= par[i] + 3 or "3putt" in acts:
                    pen += 1
                if any(a in acts for a in ["sand", "water", "ob"]):
                    pen += 1
                if title == "SuperRich" and "miss" in acts:
                    pen += 1
                pen = min(pen, 3)
                running_points[p] -= pen
                penalties[p] = pen

        point_bank += sum(penalties.values())

        if len(winners) == 1:
            w = winners[0]
            transfer = 0
            if raw[w] <= par[i] - 1:
                for p in players:
                    if p != w and running_points[p] > 0:
                        running_points[p] -= 1
                        transfer += 1
            total = point_bank + transfer
            running_points[w] += total
            log.append(f"第{i+1}洞 勝者: {w} 🎯 +{total} 點")
            point_bank = 1
        else:
            point_bank += 1
            log.append(f"第{i+1}洞 平手，銀行累積中：{point_bank} 點")

        for p in players:
            if running_points[p] >= 8:
                current_titles[p] = "SuperRich"
            elif running_points[p] >= 4:
                current_titles[p] = "Rich"
            else:
                current_titles[p] = ""

if st.button("📊 顯示比賽結果"):
    total_bet = bet_per_person * len(players)
    completed = len(st.session_state.confirmed)
    result = pd.DataFrame({
        "總點數": [running_points[p] for p in players],
        "賭金結果": [running_points[p] * total_bet - completed * bet_per_person for p in players],
        "頭銜": [current_titles[p] for p in players]
    }, index=players).sort_values("賭金結果", ascending=False)

    st.subheader("總結結果")
    st.dataframe(result.style.applymap(lambda v: "background-color: gold" if v == "SuperRich" else "background-color: lightblue" if v == "Rich" else "", subset=["頭銜"]))

    fig, ax = plt.subplots(figsize=(8, 0.5 + len(result) * 0.5))
    ax.axis("off")
    table = ax.table(cellText=result.values, colLabels=result.columns, rowLabels=result.index, cellLoc='center', loc='center')
    table.scale(1, 1.5)
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    st.image(buf, caption="LINE 可分享總表截圖")

    st.subheader("洞別說明 Log")
    for line in log:
        st.text(line)
