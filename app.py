# golf_bet_app/app.py
# 自動標示 Rich/SuperRich 狀態至下一洞欄位上方

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
if "points_per_hole" not in st.session_state:
    st.session_state.points_per_hole = [{} for _ in range(18)]

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

# 初始化分數統計
running_points = {p: 0 for p in players}

for i in range(18):
    st.subheader(f"第{i+1}洞 (Par {par[i]} / HCP {hcp[i]})")
    cols = st.columns(len(players))
    for j, p in enumerate(players):
        with cols[j]:
            # 顯示 Rich/SuperRich 狀態
            if i > 0 and st.session_state.points_per_hole[i-1].get(p):
                if st.session_state.points_per_hole[i-1][p] >= 8:
                    st.markdown(f"👑 **Super Rich Man**")
                elif st.session_state.points_per_hole[i-1][p] >= 4:
                    st.markdown(f"🏆 **Rich Man**")
            scores.loc[p, f"第{i+1}洞"] = st.number_input(f"{p} 桿數", 1, 15, par[i], key=f"score_{p}_{i}")
            events.loc[p, f"第{i+1}洞"] = ",".join(st.multiselect(f"{p} 事件", event_opts, default=["none"], key=f"event_{p}_{i}"))

    confirmed = st.checkbox(f"✅ 確認第{i+1}洞成績", key=f"confirm_{i}")
    if confirmed:
        st.session_state.confirmed.add(i)
        st.success(f"✅ 第{i+1}洞成績已確認")
    else:
        st.warning(f"⚠️ 第{i+1}洞尚未確認，將不納入點數計算")

    # 確認後進行背景點數儲存（作為下洞判斷）
    if confirmed:
        adjust = scores.copy()
        col = f"第{i+1}洞"
        raw = scores[col]
        adj = adjust[col]
        min_score = adj.min()
        winners = adj[adj == min_score].index.tolist()
        if len(winners) == 1:
            running_points[winners[0]] += 1
        st.session_state.points_per_hole[i] = running_points.copy()
