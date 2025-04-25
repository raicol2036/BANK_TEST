import streamlit as st
import pandas as pd
import os

CSV_PATH = "players.csv"
if "players" not in st.session_state:
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        st.session_state.players = df["name"].dropna().tolist()
    else:
        st.session_state.players = []

st.set_page_config(page_title="高爾夫對賭", layout="wide")
st.title("🏌️ 高爾夫BANK系統")

course_db = {
    "台中國際(東區)": {"par": [4, 4, 3, 5, 4, 4, 3, 5, 4], "handicap": [2, 8, 5, 4, 7, 1, 9, 3, 6]},
    "台中國際(西區)": {"par": [5, 4, 3, 4, 4, 3, 4, 5, 4], "handicap": [3, 6, 9, 8, 1, 4, 7, 2, 5]},
    "台中國際(中區)": {"par": [4, 4, 3, 5, 4, 4, 3, 4, 5], "handicap": [7, 2, 8, 5, 4, 1, 9, 3, 6]}
}

front = st.selectbox("前九洞球場", list(course_db.keys()), key="front")
back = st.selectbox("後九洞球場", list(course_db.keys()), key="back")
par = course_db[front]["par"] + course_db[back]["par"]
hcp = course_db[front]["handicap"] + course_db[back]["handicap"]

players = st.multiselect("選擇參賽球員", st.session_state.players, default=[])
new = st.text_input("新增球員")
if new:
    if new not in st.session_state.players:
        st.session_state.players.append(new)
        pd.DataFrame({"name": st.session_state.players}).to_csv(CSV_PATH, index=False)
        st.success(f"✅ 已新增球員 {new} 至資料庫")
    if new not in players:
        players.append(new)

handicaps = {p: st.number_input(f"{p} 差點", 0, 54, 0, key=f"hcp_{p}") for p in players}
if len(players) == 0:
    st.warning("⚠️ 請先選擇參賽球員")
    st.stop()

bet_per_person = st.number_input("單局賭金（每人）", 10, 1000, 100)

scores = pd.DataFrame(index=players, columns=[f"第{i+1}洞" for i in range(18)])
events = pd.DataFrame(index=players, columns=[f"第{i+1}洞" for i in range(18)])
event_opts = ["none", "sand", "water", "ob", "miss", "3putt or Triple", "Par on"]

running_points = {p: 0 for p in players}
current_titles = {p: "" for p in players}
log = []
point_bank = 1

for i in range(18):
    st.subheader(f"第{i+1}洞 (Par {par[i]} / HCP {hcp[i]})")
    cols = st.columns(len(players))
    winners = []  # 初始化避免未定義
    for j, p in enumerate(players):
        with cols[j]:
            if current_titles[p] == "SuperRich":
                st.markdown("👑 **Super Rich Man**")
            elif current_titles[p] == "Rich":
                st.markdown("🏆 **Rich Man**")
            scores.loc[p, f"第{i+1}洞"] = st.number_input(
                f"{p} 桿數（{running_points[p]} 點）{'🏆' if p in winners else ''}", 1, 15, par[i], key=f"score_{p}_{i}"
            )
            events.loc[p, f"第{i+1}洞"] = ",".join(
                st.multiselect(f"{p} 事件", event_opts, default=["none"], key=f"event_{p}_{i}")
            )

    confirmed = st.checkbox(f"✅ 確認第{i+1}洞成績", key=f"confirm_{i}")
    if not confirmed:
        continue

    raw = scores[f"第{i+1}洞"]
    evt = events[f"第{i+1}洞"]

    victory_map = {}
    for p1 in players:
        p1_wins = 0
        for p2 in players:
            if p1 == p2:
                continue
            adj_p1, adj_p2 = raw[p1], raw[p2]
            diff = handicaps[p1] - handicaps[p2]
            if diff > 0 and hcp[i] <= diff:
                adj_p1 -= 1
            elif diff < 0 and hcp[i] <= -diff:
                adj_p2 -= 1
            if adj_p1 < adj_p2:
                p1_wins += 1
        victory_map[p1] = p1_wins

    winners = [p for p in players if victory_map[p] == len(players) - 1]

    # ✅ 顯示勝者資訊並加上 BIRDY 圖示
    if confirmed:
        if len(winners) == 1:
            w = winners[0]
            is_birdy = raw[w] <= par[i] - 1
            bird_icon = " 🐦" if is_birdy else ""
            st.markdown(f"🏆 **本洞勝者：{w}{bird_icon}**", unsafe_allow_html=True)
        else:
            st.markdown("⚖️ **本洞平手**", unsafe_allow_html=True)

    penalties = {p: 0 for p in players}

    for p in players:
        acts = evt[p].split(",")
        title = current_titles[p]
        if title:
            pen = 0
            if raw[p] >= par[i] + 3 or "3putt" in acts:
                pen += 1
            if any(a in acts for a in ["sand", "miss", "water", "ob"]):
                pen += 1
            if title == "SuperRich" and "Par on" in acts:
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
        log.append(f"第{i+1}洞 勝者: {w} 🎯 +{total} 點 🏆")
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
    completed = len([i for i in range(18) if f"confirm_{i}" in st.session_state and st.session_state[f"confirm_{i}"]])
    result = pd.DataFrame({
        "總點數": [running_points[p] for p in players],
        "賭金結果": [running_points[p] * total_bet - completed * bet_per_person for p in players],
        "頭銜": [current_titles[p] for p in players]
    }, index=players).sort_values("賭金結果", ascending=False)

    st.subheader("總結結果")
    st.dataframe(result)

    st.subheader("洞別說明 Log")
    for line in log:
        st.text(line)