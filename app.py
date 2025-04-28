
import streamlit as st
import pandas as pd
import os

# --- 初始化資料 ---
CSV_PATH = "players.csv"
if "players" not in st.session_state:
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        st.session_state.players = df["name"].dropna().tolist()
    else:
        st.session_state.players = []

st.set_page_config(page_title="🏌️ 高爾夫BANK系統", layout="wide")
st.title("🏌️ 高爾夫BANK系統")

# --- 模式選擇 ---
mode = st.radio("選擇模式", ["主控操作端", "隊員查看端"])

# --- 球場設定 ---
course_db = {
    "台中國際(東區)": {"par": [4,4,3,5,4,4,3,5,4], "handicap": [2,8,5,4,7,1,9,3,6]},
    "台中國際(西區)": {"par": [5,4,3,4,4,3,4,5,4], "handicap": [3,6,9,8,1,4,7,2,5]},
    "台中國際(中區)": {"par": [4,4,3,5,4,4,3,4,5], "handicap": [7,2,8,5,4,1,9,3,6]}
}

front = st.selectbox("前九洞球場", list(course_db.keys()), key="front")
back = st.selectbox("後九洞球場", list(course_db.keys()), key="back")
par = course_db[front]["par"] + course_db[back]["par"]
hcp = course_db[front]["handicap"] + course_db[back]["handicap"]

# --- 球員設定 ---
players = st.multiselect("選擇參賽球員（最多4位）", st.session_state.players, max_selections=4)

new = st.text_input("新增球員")
if new:
    if new not in st.session_state.players:
        st.session_state.players.append(new)
        pd.DataFrame({"name": st.session_state.players}).to_csv(CSV_PATH, index=False)
        st.success(f"✅ 已新增球員 {new} 至資料庫")
    if new not in players and len(players) < 4:
        players.append(new)

if len(players) == 0:
    st.warning("⚠️ 請先選擇至少一位球員")
    st.stop()

handicaps = {p: st.number_input(f"{p} 差點", 0, 54, 0, key=f"hcp_{p}") for p in players}
bet_per_person = st.number_input("單局賭金（每人）", 10, 1000, 100)

# --- 遊戲初始化 ---
scores = pd.DataFrame(index=players, columns=[f"第{i+1}洞" for i in range(18)])
events = pd.DataFrame(index=players, columns=[f"第{i+1}洞" for i in range(18)])
event_opts_display = ["下沙", "下水", "OB", "丟球", "加3或3推", "Par on"]
event_translate = {"下沙": "sand", "下水": "water", "OB": "ob", "丟球": "miss", "加3或3推": "3putt_or_plus3", "Par on": "par_on"}
penalty_keywords = ["sand", "water", "ob", "miss", "3putt_or_plus3"]

running_points = {p: 0 for p in players}
current_titles = {p: "" for p in players}
log = []
point_bank = 1

# --- 主流程 ---
for i in range(18):
    st.subheader(f"第{i+1}洞 (Par {par[i]} / HCP {hcp[i]})")
    cols = st.columns(len(players))

    if mode == "主控操作端":
        for j, p in enumerate(players):
            with cols[j]:
                if current_titles[p] == "SuperRich":
                    st.markdown("👑 **Super Rich Man**")
                elif current_titles[p] == "Rich":
                    st.markdown("🏆 **Rich Man**")
                scores.loc[p, f"第{i+1}洞"] = st.number_input(f"{p} 桿數（{running_points[p]} 點）", 1, 15, par[i], key=f"score_{p}_{i}")
                selected_display = st.multiselect(f"{p} 事件", event_opts_display, key=f"event_{p}_{i}")
                selected_internal = [event_translate[d] for d in selected_display]
                events.loc[p, f"第{i+1}洞"] = selected_internal

        confirmed = st.checkbox(f"✅ 確認第{i+1}洞成績", key=f"confirm_{i}")
        if not confirmed:
            continue

        raw = scores[f"第{i+1}洞"]
        evt = events[f"第{i+1}洞"]

        start_of_hole_bank = point_bank  # 先記錄這洞開始時的bank

        # 先事件懲罰
        event_penalties = {p: 0 for p in players}
        for p in players:
            acts = evt[p] if isinstance(evt[p], list) else []
            pen = sum(1 for act in acts if act in penalty_keywords)
            if current_titles[p] == "SuperRich" and "par_on" in acts:
                pen += 1
            pen = min(pen, 3)
            running_points[p] -= pen
            event_penalties[p] = pen

        # 判定勝負
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
        total_penalty_this_hole = sum(event_penalties.values())

        if len(winners) == 1:
            w = winners[0]
            is_birdy = raw[w] <= par[i] - 1
            bird_icon = " 🐦" if is_birdy else ""

            gain_points = point_bank
            birdie_penalties = {p: 0 for p in players}
            if is_birdy:
                for p in players:
                    if p != w and running_points[p] > 0:
                        running_points[p] -= 1
                        gain_points += 1
                        birdie_penalties[p] += 1

            running_points[w] += gain_points

            winner_text = f"🏆 本洞勝者：{w}{bird_icon}（取得 +{gain_points} 點）"
            penalty_texts = []
            for p in players:
                total_penalty = event_penalties.get(p, 0) + birdie_penalties.get(p, 0)
                if total_penalty > 0:
                    penalty_texts.append(f"{p} 扣 {total_penalty}點")
            if penalty_texts:
                winner_text += "｜" + "；".join(penalty_texts)
            st.markdown(f"**{winner_text}**", unsafe_allow_html=True)
            log.append(f"第{i+1}洞 勝者: {w} 🎯 +{gain_points}點")
            point_bank = 1

        else:
            add_this_hole = 1 + total_penalty_this_hole
            bank_after_this_hole = start_of_hole_bank + add_this_hole
            penalty_texts = []
            for p in players:
                total_penalty = event_penalties.get(p, 0)
                if total_penalty > 0:
                    penalty_texts.append(f"{p} 扣 {total_penalty}點")
            if penalty_texts:
                penalty_summary = "｜" + "；".join(penalty_texts)
            else:
                penalty_summary = ""
            st.markdown(f"⚖️ **本洞平手{penalty_summary}（Bank累積 {bank_after_this_hole}點）**", unsafe_allow_html=True)
            log.append(f"第{i+1}洞 平手，銀行累積 {bank_after_this_hole}點")
            point_bank = bank_after_this_hole

        for p in players:
            if running_points[p] >= 8:
                current_titles[p] = "SuperRich"
            elif running_points[p] >= 4:
                current_titles[p] = "Rich"
            else:
                current_titles[p] = ""

    else:
        if f"confirm_{i}" in st.session_state and st.session_state[f"confirm_{i}"]:
            st.success("✅ 本洞成績已完成")
        else:
            st.warning("⌛ 尚未完成")

if st.button("📊 顯示比賽結果"):
    total_bet = bet_per_person * len(players)
    completed = len([i for i in range(18) if f"confirm_{i}" in st.session_state and st.session_state[f"confirm_{i}"]])
    result = pd.DataFrame({
        "總點數": [running_points[p] for p in players],
        "賭金結果": [running_points[p]*total_bet - completed*bet_per_person for p in players],
        "頭銜": [current_titles[p] for p in players]
    }, index=players).sort_values("賭金結果", ascending=False)

    st.subheader("總結結果")
    st.dataframe(result)

    st.subheader("洞別說明 Log")
    for line in log:
        st.text(line)
