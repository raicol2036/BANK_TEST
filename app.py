# golf_bet_app/app.py
# 高爾夫對賭系統（支援 18 洞、差點讓桿、平手點數累積、Birdy 加點、洞別確認、LINE 分享圖像、單洞賭金修正）

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

st.set_page_config(page_title="高爾夫對賭", layout="wide")

st.title("🏌️ 高爾夫對賭賽事系統")

# 初始資料
course_db = {
    "台中國際(東區)": {"par": [4, 4, 3, 5, 4, 4, 3, 5, 4], "handicap": [2, 8, 5, 4, 7, 1, 9, 3, 6]},
    "台中國際(西區)": {"par": [5, 4, 3, 4, 4, 3, 4, 5, 4], "handicap": [3, 6, 9, 8, 1, 4, 7, 2, 5]},
    "台中國際(中區)": {"par": [4, 4, 3, 5, 4, 4, 3, 4, 5], "handicap": [7, 2, 8, 5, 4, 1, 9, 3, 6]}
}

if "players" not in st.session_state:
    st.session_state.players = ["Lee", "Joye", "Raicol", "Jerry"]
if "confirmed" not in st.session_state:
    st.session_state.confirmed = set()

# 球場選擇
st.header("球場設定")
front = st.selectbox("前九洞球場", list(course_db.keys()), key="front")
back = st.selectbox("後九洞球場", list(course_db.keys()), key="back")
par = course_db[front]["par"] + course_db[back]["par"]
hcp = course_db[front]["handicap"] + course_db[back]["handicap"]

# 球員設定
players = st.multiselect("選擇參賽球員", st.session_state.players, default=st.session_state.players[:4])
new = st.text_input("新增球員")
if new and new not in st.session_state.players:
    st.session_state.players.append(new)
    players.append(new)

handicaps = {p: st.number_input(f"{p} 差點", 0, 54, 0, key=f"hcp_{p}") for p in players}
bet = st.number_input("每點賭金 (元)", 10, 1000, 100)

# 分數與事件輸入
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

# 計算邏輯
if st.button("🔍 計算總結果"):
    let_dict = {
        p1: {
            p2: set(sorted(range(18), key=lambda x: hcp[x])[:abs(handicaps[p2] - handicaps[p1])])
            for p2 in players if p1 != p2
        } for p1 in players
    }

    adjust = scores.copy()
    for i in range(18):
        for p in players:
            let = sum(1 for opp in players if p in let_dict.get(opp, {}) and i in let_dict[opp][p])
            adjust.loc[p, f"第{i+1}洞"] -= let

    point_bank = 1
    points = {p: 0 for p in players}
    titles = {p: None for p in players}
    log = []
    money = {p: 0 for p in players}  # 💰 每位賭金計算

    for i in range(18):
        if i not in st.session_state.confirmed:
            log.append(f"第{i+1}洞 尚未確認，略過")
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
            if points[p] >= 8:
                titles[p] = "SuperRich"
            elif points[p] >= 4:
                titles[p] = "Rich"
            else:
                titles[p] = None
            if titles[p]:
                pen = 0
                if raw_score >= par[i] + 3 or "3putt" in e:
                    pen += 1
                if any(x in e for x in ["sand", "water", "ob"]):
                    pen += 1
                if titles[p] == "SuperRich" and "miss" in e:
                    pen += 1
                pen = min(pen, 3)
                points[p] -= pen
                penalties[p] = pen
                if points[p] <= 0:
                    titles[p] = None
                elif titles[p] == "SuperRich" and points[p] < 4:
                    titles[p] = "Rich"

        point_bank += sum(penalties.values())

        if len(winners) == 1:
            w = winners[0]
            birdy = raw[w] <= par[i] - 1
            transfer = 0
            if birdy:
                for p in players:
                    if p != w and points[p] > 0:
                        points[p] -= 1
                        transfer += 1

            actual_bonus = point_bank + transfer
            points[w] += actual_bonus
            losers = [p for p in players if p != w]
            money[w] += len(losers) * bet
            for p in losers:
                money[p] -= bet

            log.append(f"第{i+1}洞 勝者: {w} 🎯 +{actual_bonus} 點 / 賺 {len(losers)*bet} 元")
            point_bank = 1
        else:
            log.append(f"第{i+1}洞 平手，銀行累積中：{point_bank} 點")

    st.header("比賽結果總表")
    res = pd.DataFrame({
        "總點數": [points[p] for p in players],
        "賭金結果": [money[p] for p in players],
        "頭銜": [titles[p] or "" for p in players]
    }, index=players).sort_values("賭金結果", ascending=False)

    st.dataframe(res.style.applymap(lambda v: "background-color: gold" if v == "SuperRich" else "background-color: lightblue" if v == "Rich" else "", subset=["頭銜"]))

    fig, ax = plt.subplots(figsize=(8, 0.5 + len(res) * 0.5))
    ax.axis("off")
    table = ax.table(cellText=res.values, colLabels=res.columns, rowLabels=res.index, cellLoc='center', loc='center')
    table.scale(1, 1.5)
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    st.image(buf, caption="LINE 可分享的總表圖像")

    st.subheader("洞別說明 Log")
    for line in log:
        st.text(line)
