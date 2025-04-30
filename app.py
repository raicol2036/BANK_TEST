
import streamlit as st
import pandas as pd
import os

# --- 初始化資料 ---
CSV_PATH = "players.csv"
COURSE_DB_PATH = "course_db.csv"

if "players" not in st.session_state:
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        st.session_state.players = df["name"].dropna().tolist()
    else:
        st.session_state.players = []

if os.path.exists(COURSE_DB_PATH):
    course_df = pd.read_csv(COURSE_DB_PATH)
else:
    st.error("找不到 course_db.csv！請先準備好球場資料。")
    st.stop()

st.set_page_config(page_title="🏌️ 高爾夫BANK系統", layout="wide")
st.title("🏌️ 高爾夫BANK系統")

# --- 模式設定 (直接隱藏，預設為主控端) ---
if "mode" not in st.session_state:
    st.session_state.mode = "主控操作端"
mode = st.session_state.mode

# --- 球場選擇 ---
course_options = course_df["course_name"].unique().tolist()
selected_course = st.selectbox("選擇球場", course_options)

filtered_area = course_df[course_df["course_name"] == selected_course]["area"].unique().tolist()
front_area = st.selectbox("前九洞區域", filtered_area, key="front_area")
back_area = st.selectbox("後九洞區域", filtered_area, key="back_area")

def get_course_info(cname, area):
    temp = course_df[(course_df["course_name"] == cname) & (course_df["area"] == area)]
    temp = temp.sort_values("hole")
    return temp["par"].tolist(), temp["hcp"].tolist()

front_par, front_hcp = get_course_info(selected_course, front_area)
back_par, back_hcp = get_course_info(selected_course, back_area)
par = front_par + back_par
hcp = front_hcp + back_hcp

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
hole_logs = []
point_bank = 1

# --- 主流程 ---
for i in range(18):
    if mode == "隊員查看端" and not (f"confirm_{i}" in st.session_state and st.session_state[f"confirm_{i}"]):
        continue

    st.subheader(f"第{i+1}洞 (Par {par[i]} / HCP {hcp[i]})")

    if mode == "主控操作端":
        cols = st.columns(len(players))
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

    if f"confirm_{i}" in st.session_state and st.session_state[f"confirm_{i}"]:
        raw = scores[f"第{i+1}洞"]
        evt = events[f"第{i+1}洞"]
        start_of_hole_bank = point_bank

        event_penalties = {p: 0 for p in players}
        for p in players:
            acts = evt[p] if isinstance(evt[p], list) else []
            pen = 0
            if current_titles[p] in ["Rich", "SuperRich"]:
                pen = sum(1 for act in acts if act in penalty_keywords)
                if current_titles[p] == "SuperRich" and "par_on" in acts:
                    pen += 1
                pen = min(pen, 3)
            running_points[p] -= pen
            event_penalties[p] = pen

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

        penalty_info = []
        for p in players:
            if event_penalties[p] > 0:
                penalty_info.append(f"{p} 扣 {event_penalties[p]}點")
        penalty_summary = "｜".join(penalty_info) if penalty_info else ""

        if len(winners) == 1:
            w = winners[0]
            is_birdy = raw[w] <= par[i] - 1
            bird_icon = " 🐦" if is_birdy else ""
            gain_points = point_bank
            if is_birdy:
                for p in players:
                    if p != w and running_points[p] > 0:
                        running_points[p] -= 1
                        gain_points += 1
            running_points[w] += gain_points
            hole_log = f"🏆 第{i+1}洞勝者：{w}{bird_icon}（取得+{gain_points}點）{('｜' + penalty_summary) if penalty_summary else ''}"
            point_bank = 1
        else:
            add_this_hole = 1 + total_penalty_this_hole
            bank_after_this_hole = start_of_hole_bank + add_this_hole
            hole_log = f"⚖️ 第{i+1}洞平手{('｜' + penalty_summary) if penalty_summary else ''}（下洞累積 {bank_after_this_hole}點）"
            point_bank = bank_after_this_hole

        st.markdown(hole_log)
        hole_logs.append(hole_log)

        for p in players:
            if current_titles[p] == "SuperRich":
                if running_points[p] <= 4:
                    current_titles[p] = "Rich"
            elif current_titles[p] == "Rich":
                if running_points[p] == 0:
                    current_titles[p] = ""
            else:
                if running_points[p] >= 8:
                    current_titles[p] = "SuperRich"
                elif running_points[p] >= 4:
                    current_titles[p] = "Rich"
                else:
                    current_titles[p] = ""

# --- 總結結果 ---
st.subheader("📊 總結結果")
total_bet = bet_per_person * len(players)
completed = len([i for i in range(18) if st.session_state.get(f"confirm_{i}", False)])
result = pd.DataFrame({
    "總點數": [running_points[p] for p in players],
    "賭金結果": [running_points[p] * total_bet - completed * bet_per_person for p in players],
    "頭銜": [current_titles[p] for p in players]
}, index=players).sort_values("賭金結果", ascending=False)
st.dataframe(result)

st.subheader("📖 洞別說明 Log")
for line in hole_logs:
    st.text(line)
