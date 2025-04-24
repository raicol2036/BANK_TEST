import streamlit as st
import pandas as pd
import uuid
import json
import os

st.set_page_config(page_title="高爾夫對賭計分器", layout="wide")
st.title("🏌️ 高爾夫對賭賽事系統（18洞版）")

# 初始球場與球員資料
course_db = {
    "台中國際(東區)": {
        "par": [4, 4, 3, 5, 4, 4, 3, 5, 4],
        "handicap": [2, 8, 5, 4, 7, 1, 9, 3, 6]
    },
    "台中國際(西區)": {
        "par": [5, 4, 3, 4, 4, 3, 4, 5, 4],
        "handicap": [3, 6, 9, 8, 1, 4, 7, 2, 5]
    },
    "台中國際(中區)": {
        "par": [4, 4, 3, 5, 4, 4, 3, 4, 5],
        "handicap": [7, 2, 8, 5, 4, 1, 9, 3, 6]
    }
}

if "players" not in st.session_state:
    st.session_state.players = ["Lee", "Joye", "Raicol", "Jerry", "Landam", "Jason", "Jovie"]

# 球場選擇
st.subheader("球場選擇（前九 + 後九）")
front_course_name = st.selectbox("選擇前九洞球場：", list(course_db.keys()), key="front")
back_course_name = st.selectbox("選擇後九洞球場：", list(course_db.keys()), index=1, key="back")
front_course = course_db[front_course_name]
back_course = course_db[back_course_name]

# 組合18洞資料
course_data = {
    "par": front_course["par"] + back_course["par"],
    "handicap": front_course["handicap"] + back_course["handicap"]
}

# 球員與差點
selected_players = st.multiselect("選擇參賽球員：", st.session_state.players)
new_player = st.text_input("新增球員（可留空）")
if new_player and new_player not in st.session_state.players:
    st.session_state.players.append(new_player)
    selected_players.append(new_player)

handicaps = {}
if selected_players:
    st.subheader("輸入差點與賭金設定")
    for p in selected_players:
        handicaps[p] = st.number_input(f"{p} 的差點：", min_value=0, max_value=54, value=0, key=f"hcp_{p}")
    bet = st.number_input("每點賭金（比賽前設定）：", value=50)

# 計分與事件輸入
if selected_players:
    st.subheader("輸入每洞桿數與事件（18洞）")
    score_data = {"玩家": selected_players}
    event_data = {"玩家": selected_players}
    event_options = ["none", "sand", "water", "ob", "miss", "3putt"]
    for i in range(18):
        score_data[f"第{i+1}洞"] = []
        event_data[f"第{i+1}洞"] = []
        st.markdown(f"### 第{i+1}洞 (Par {course_data['par'][i]})")
        cols = st.columns(len(selected_players))
        for idx, p in enumerate(selected_players):
            with cols[idx]:
                score = st.number_input(f"{p} 桿數", min_value=1, max_value=15, value=course_data['par'][i], key=f"score_{p}_{i}")
                events = st.multiselect(f"{p} 事件", options=event_options, default=["none"], key=f"event_{p}_{i}")
                score_data[f"第{i+1}洞"].append(score)
                event_data[f"第{i+1}洞"].append(",".join(e for e in events if e != "none"))

    if st.button("🔍 計算與儲存結果"):
        scores_df = pd.DataFrame(score_data).set_index("玩家")
        events_df = pd.DataFrame(event_data).set_index("玩家")

        def calc_let_holes(h1, h2, hcp_list):
            front = sorted(range(9), key=lambda i: hcp_list[i])[:max(h2 - h1, 0)//2]
            back = sorted(range(9, 18), key=lambda i: hcp_list[i])[:max(h2 - h1, 0)-len(front)]
            return set(front + back)

        let_strokes = {
            p1: {
                p2: calc_let_holes(handicaps[p1], handicaps[p2], course_data["handicap"])
                for p2 in selected_players if p1 != p2
            }
            for p1 in selected_players
        }

        adjusted = pd.DataFrame(index=selected_players, columns=[f"第{i+1}洞" for i in range(18)])
        for p in selected_players:
            for i in range(18):
                let_count = sum(1 for opp in selected_players if p in let_strokes[opp] and i in let_strokes[opp][p])
                adjusted.at[p, f"第{i+1}洞"] = scores_df.at[p, f"第{i+1}洞"] - let_count

        points = {p: 0 for p in selected_players}
        titles = {p: None for p in selected_players}
        result_rows = []

        for i in range(18):
            col = f"第{i+1}洞"
            min_score = adjusted[col].min()
            winners = adjusted[adjusted[col] == min_score].index.tolist()
            penalties = {p: 0 for p in selected_players}

            for p in selected_players:
                raw = scores_df.at[p, col]
                event_set = set(e.strip() for e in events_df.at[p, col].lower().split(",") if e.strip())
                if points[p] >= 8:
                    titles[p] = "SuperRich"
                elif points[p] >= 4:
                    titles[p] = "Rich"
                else:
                    titles[p] = None
                if titles[p]:
                    pen = 0
                    if raw >= course_data["par"][i] + 3 or "3putt" in event_set:
                        pen += 1
                    if any(e in event_set for e in ["sand", "water", "ob"]):
                        pen += 1
                    if titles[p] == "SuperRich" and "miss" in event_set:
                        pen += 1
                    penalties[p] = min(pen, 3)
                    points[p] -= penalties[p]
                    if points[p] <= 0:
                        titles[p] = None
                    elif titles[p] == "SuperRich" and points[p] < 4:
                        titles[p] = "Rich"

            bonus = sum(penalties.values())
            if len(winners) == 1:
                points[winners[0]] += 1 + bonus
                st.markdown(f"**第{i+1}洞：{winners[0]} 獲得 {1 + bonus} 點**")
            else:
                st.markdown(f"第{i+1}洞：平手 無人得點")

        st.subheader("賽事總結")
        results = []
        for p in selected_players:
            cash = points[p] * bet * len(selected_players) - bet * 18
            results.append({"玩家": p, "總點數": points[p], "賭金結果": cash, "頭銜": titles[p]})

        df = pd.DataFrame(results)
        st.dataframe(df.style.applymap(lambda v: "background-color: gold" if v == "SuperRich" else "background-color: lightblue" if v == "Rich" else "", subset=["頭銜"]))

        match_id = str(uuid.uuid4())
        match_data = {
            "id": match_id,
            "players": selected_players,
            "handicaps": handicaps,
            "scores": scores_df.to_dict(),
            "events": events_df.to_dict(),
            "points": points,
            "titles": titles,
            "bet": bet,
            "result": results,
            "course": {"front": front_course_name, "back": back_course_name}
        }
        os.makedirs("matches", exist_ok=True)
        with open(f"matches/{match_id}.json", "w", encoding="utf-8") as f:
            json.dump(match_data, f, ensure_ascii=False, indent=2)

        st.success("✅ 賽事已儲存！")
        st.code(f"分享連結 ID：{match_id}")
