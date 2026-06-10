import streamlit as st
import pandas as pd
import numpy as np
import os
import itertools
import matplotlib.pyplot as plt
import json

# --- 画面設定 ---
st.set_page_config(page_title="競艇 類似レース予想 AI", layout="centered")

# --- 🧠 1. 企画レースマスタの読み込み ---
if os.path.exists("kikaku_master.json"):
    with open("kikaku_master.json", "r", encoding="utf-8") as f:
        kikaku_master = json.load(f)
else:
    kikaku_master = {}

# 24競艇場のマスタデータ
venues_map = {
    "01": "01_桐生", "02": "02_戸田", "03": "03_江戸川", "04": "04_平和島", 
    "05": "05_多摩川", "06": "06_浜名湖", "07": "07_蒲郡", "08": "08_常滑", 
    "09": "09_津", "10": "10_三国", "11": "11_びわこ", "12": "12_住之江",
    "13": "13_尼崎", "14": "14_鳴門", "15": "15_丸亀", 
    "16": "16_児島", "17": "17_宮島", "18": "18_徳山", "19": "19_下関", 
    "20": "20_若松", "21": "21_芦屋", "22": "22_福岡", "23": "23_唐津", 
    "24": "24_大村"
}
venues_list = sorted(list(venues_map.values()))

# --- 🔄 2. セッション状態（ページ跨ぎのデータ保持）の初期化 ---
if "target_venue" not in st.session_state:
    st.session_state["target_venue"] = "09_津" 
if "target_rno" not in st.session_state:
    st.session_state["target_rno"] = "1"
if "auto_search" not in st.session_state:
    st.session_state["auto_search"] = False
if "toast_msg" not in st.session_state:
    st.session_state["toast_msg"] = None

# 💡 タブ選択状態をStreamlitのWidget Stateと完全に結びつけるための初期化
if "current_tab" not in st.session_state:
    st.session_state["current_tab"] = "🔍 自分で分析・予想"

# --- ⚡ 3. AI厳選用：超高速一括計算キャッシュロジック ---
@st.cache_data(ttl=1800) 
def generate_ai_ranking_cached():
    if not os.path.exists("real_time_出走表.csv"):
        return None
        
    df_today = pd.read_csv("real_time_出走表.csv")
    all_race_results = []
    
    for _, row in df_today.iterrows():
        jcd_int = int(row['jcd'])
        jcd_str = f"{jcd_int:02d}"
        venue_full_name = venues_map.get(jcd_str)
        
        if not venue_full_name:
            continue
            
        csv_file = f"{venue_full_name}.csv"
        if not os.path.exists(csv_file):
            continue
        
        df_past = pd.read_csv(csv_file, encoding='utf-8-sig')
        past_patterns = df_past[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values
        
        rel_rates = [
            row['相対勝率_1'], row['相対勝率_2'], row['相対勝率_3'],
            row['相対勝率_4'], row['相対勝率_5'], row['相対勝率_6']
        ]
        
        distances = np.linalg.norm(past_patterns - np.array(rel_rates), axis=1)
        df_past['tmp_dist'] = distances
        similar_100 = df_past.sort_values('tmp_dist').head(100).copy()
        similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)
        
        honmei_count = (similar_100['p'] < 1500).sum()
        manshu_count = (similar_100['p'] >= 10000).sum()
        in_escape_count = (similar_100['r1'] == 1.0).sum()
        
        all_race_results.append({
            "venue": venue_full_name,
            "jcd": jcd_str,
            "rno": int(row['r']),
            "honmei_rate": honmei_count,
            "manshu_rate": manshu_count,
            "in_escape_rate": in_escape_count
        })
        
    return pd.DataFrame(all_race_results) if all_race_results else None


# ====================================================
# 📱 スマホ最適化カスタムタブ（バグ完全修正版）
# ====================================================
# key="current_tab" を指定することで、プログラム側からの書き換えと100%同期します
st.radio(
    "ナビゲーション",
    ["🔍 自分で分析・予想", "🤖 本日のAI厳選"],
    key="current_tab",
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown("<br>", unsafe_allow_html=True)


# ====================================================
# 🔍 タブ1: 自分で分析・予想
# ====================================================
if st.session_state["current_tab"] == "🔍 自分で分析・予想":
    
    # 💡 UI/UX改善: ジャンプしてきた時に画面に通知をふわっと出す
    if st.session_state["toast_msg"]:
        st.toast(st.session_state["toast_msg"])
        st.session_state["toast_msg"] = None # 表示したらクリア
        
    st.markdown("### 1. レース情報の指定")
    col1, col2 = st.columns(2)

    with col1:
        v_idx = venues_list.index(st.session_state["target_venue"]) if st.session_state["target_venue"] in venues_list else 8
        selected_venue = st.selectbox("📌 競艇場", venues_list, index=v_idx)
        jcd_str = selected_venue.split("_")[0] 

    with col2:
        r_options = [str(i) for i in range(1, 13)]
        r_idx = r_options.index(st.session_state["target_rno"]) if st.session_state["target_rno"] in r_options else 0
        rno_str = st.selectbox("🚤 レース番号", r_options, index=r_idx)

    st.markdown("---")

    # --- スマホ特化型フォーメーション入力 ---
    st.markdown("### 🎯 あなたの予想（フォーメーション）")
    st.caption("※入力しなくても類似レースの検索は可能です")

    c1, c2, c3 = st.columns(3)
    boat_options = [1, 2, 3, 4, 5, 6]

    with c1:
        st.markdown("#### 🥇 1着")
        all_1 = st.toggle("【全】", key="m_all_1")
        pred_1 = boat_options if all_1 else st.multiselect("1着", boat_options, placeholder="選択..", label_visibility="collapsed", key="sel_1")

    with c2:
        st.markdown("#### 🥈 2着")
        all_2 = st.toggle("【全】", key="m_all_2")
        pred_2 = boat_options if all_2 else st.multiselect("2着", boat_options, placeholder="選択..", label_visibility="collapsed", key="sel_2")

    with c3:
        st.markdown("#### 🥉 3着")
        all_3 = st.toggle("【全】", key="m_all_3")
        pred_3 = boat_options if all_3 else st.multiselect("3着", boat_options, placeholder="選択..", label_visibility="collapsed", key="key_3")

    # 💡 UI/UX改善: フォーメーションを一発で白紙に戻すリセットボタン
    if st.button("❌ 予想入力をすべてクリアする", use_container_width=True):
        for k in ["sel_1", "sel_2", "key_3", "m_all_1", "m_all_2", "m_all_3"]:
            if k in st.session_state:
                if "all" in k:
                    st.session_state[k] = False
                else:
                    st.session_state[k] = []
        st.rerun()

    st.markdown("---")

    search_triggered = st.button("類似レースを検索して分析する 🔍", use_container_width=True)
    
    # AI厳選からの自動検索ジャンプ
    if st.session_state["auto_search"]:
        search_triggered = True
        st.session_state["auto_search"] = False 

    if search_triggered:
        if os.path.exists("real_time_出走表.csv"):
            df_today = pd.read_csv("real_time_出走表.csv")
            df_target = df_today[(df_today['jcd'] == int(jcd_str)) & (df_today['r'] == int(rno_str))]
            
            file_path = f"{selected_venue}.csv"
            if df_target.empty:
                if os.path.exists(file_path):
                    df_target = pd.read_csv(file_path).sample(n=1)
                    st.warning("⚠️ 当日出走表に該当レースがなかったため、過去データから形状の近いレースを代用して解析しています。")
            
            if not df_target.empty and os.path.exists(file_path):
                mock_row = df_target.iloc[0]
                rel_rates = [
                    mock_row['相対勝率_1'], mock_row['相対勝率_2'], mock_row['相対勝率_3'],
                    mock_row['相対勝率_4'], mock_row['相対勝率_5'], mock_row['相対勝率_6']
                ]
                
                df_past = pd.read_csv(file_path, encoding='utf-8-sig')
                past_patterns = df_past[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values

                df_past['距離'] = np.linalg.norm(past_patterns - np.array(rel_rates), axis=1)
                similar_100 = df_past.sort_values('距離').head(100).copy()

                def make_result_str(row):
                    return f"{int(row['r1'])}-{int(row['r2'])}-{int(row['r3'])}"
                similar_100['3連単'] = similar_100.apply(make_result_str, axis=1)
                similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)

                # あなたのフォーメーション予想結果
                if pred_1 and pred_2 and pred_3:
                    st.markdown("### 🎯 あなたのフォーメーション予想結果")
                    raw_combos = list(itertools.product(pred_1, pred_2, pred_3))
                    valid_combos = [f"{c[0]}-{c[1]}-{c[2]}" for c in raw_combos if len(set(c)) == 3]
                    
                    if valid_combos:
                        my_hits = similar_100[similar_100['3連単'].isin(valid_combos)]
                        my_count = len(my_hits)
                        st.info(f"あなたの買い目（計**{len(valid_combos)}点**）の合算出現率: **{my_count}%**")
                        
                        if my_count > 0:
                            st.markdown("#### 🌟 予想内の頻出着順ベスト5")
                            my_best = my_hits['3連単'].value_counts().head(5)
                            for i, (result, count) in enumerate(my_best.items()):
                                st.success(f"**第{i+1}位：【 {result} 】** （出現率: {count}%）")
                        else:
                            st.warning("あなたの予想は、過去の類似100レースでは1度も発生していません。来れば大穴です！")
                    else:
                        st.error("有効な買い目がありません（同じ号艇が重複して選択されています）。")
                    st.markdown("---")

                # 全体の頻出着順ベスト3
                st.markdown("## 🏆 全体の頻出着順ベスト3")
                top3 = similar_100['3連単'].value_counts().head(3)
                for i, (result, count) in enumerate(top3.items()):
                    st.markdown(f"**第{i+1}位: 【 {result} 】** （出現率: {count}%）")
                st.markdown("---")

                # 配当分布グラフ
                st.markdown("### 📈 類似100レースの配当分布（金額帯）")
                bins = [0, 1500, 3000, 5000, 10000, 30000, 1000000]
                labels = ['~1.5k', '1.5k~3k', '3k~5k', '5k~10k', '10k~30k', '30k~']
                similar_100['配当帯'] = pd.cut(similar_100['p'], bins=bins, labels=labels, right=False)
                
                dist = similar_100['配当帯'].value_counts().reindex(labels).fillna(0)
                
                fig, ax = plt.subplots(figsize=(6, 3.2), facecolor='none')
                ax.set_facecolor('none')
                ax.bar(dist.index, dist.values, color='#1f77b4', alpha=0.8, edgecolor='#114466')
                ax.set_ylim(0, 100)
                ax.tick_params(colors='#888888', labelsize=9)
                for spine in ax.spines.values():
                    spine.set_color('#444444')
                    
                st.pyplot(fig, clear_figure=True)
                st.caption("※縦軸はレース数（最大100回）。右に山があるほど荒れやすいパターンです。")
                st.markdown("---")

                # 【指定位置】レースの性質（ステータス）をグラフの直下に配置
                is_kikaku_slot = int(rno_str) in kikaku_master.get(jcd_str, {}).get("kikaku_slots", [])
                is_under_8r = int(rno_str) <= 8
                
                honmei_pct = (similar_100['p'] < 1500).sum()
                manshu_pct = (similar_100['p'] >= 10000).sum()
                
                if is_kikaku_slot and is_under_8r and (similar_100['r1'] == 1.0).sum() >= 65:
                    status_text = "🔵 企画通り（シード選手が番組の意図通りに逃げ切る確率が極めて高い戦い）"
                elif honmei_pct >= 40:
                    status_text = "🟢 ド安定（過去のデータ上、上位人気のカチカチ決着になる確率が非常に高い戦い）"
                elif manshu_pct >= 20:
                    status_text = "🔴 大荒れ注意（イン信頼度が低く、万舟や高配当が飛び出す危険な波乱パターン）"
                elif honmei_pct >= 25:
                    status_text = "🟡 普通・標準（平均的な本命戦。展開ひとつで中穴へのシフトもあり得る状態）"
                else:
                    status_text = "⚪ 波乱含み（本命の信頼度がやや低く、中穴〜大穴の気配が漂うレース）"
                    
                st.markdown(f"#### 📊 レースの性質： {status_text}")

            else:
                st.error(f"過去データファイルが見つかりません: {file_path}")
        else:
            st.error("当日出走表ファイル（real_time_出走表.csv）が配置されていません。")

# ====================================================
# 🤖 タブ2: 本日のAI厳選
# ====================================================
elif st.session_state["current_tab"] == "🤖 本日のAI厳選":
    st.markdown("### 🌟 AIがデータから見つけた本日の勝負レース（全場スキャン）")
    st.caption("本日（明日）開催される全競艇場の全レースをGitHub上の出走表から一括解析し、全体の総合トップ5を推薦します。")
    
    df_all_res = generate_ai_ranking_cached()
    
    if df_all_res is None:
        st.error("当日出走表データ（real_time_出走表.csv）が見つからないか、解析可能な組み合わせデータがありません。")
    else:
        # 1. 全場一括：ド安定ベスト5
        st.markdown("#### 🟢 鉄板！ド安定レース（全場総合トップ5）")
        df_stable = df_all_res.sort_values("honmei_rate", ascending=False).head(5)
        for _, row in df_stable.iterrows():
            venue_name_only = row['venue'].split('_')[1]
            btn_label = f"【{venue_name_only} {int(row['rno'])}R】 本命率: {int(row['honmei_rate'])}% ➔"
            if st.button(btn_label, key=f"all_btn_st_{row['venue']}_{row['rno']}"):
                st.session_state["target_venue"] = row['venue']
                st.session_state["target_rno"] = str(int(row['rno']))
                st.session_state["current_tab"] = "🔍 自分で分析・予想" # 👈 🔥強制ワープ
                st.session_state["auto_search"] = True
                st.session_state["toast_msg"] = f"🏃‍♂️ AI厳選から 【{venue_name_only} {int(row['rno'])}R】 をロードしました！"
                st.rerun()
                
        st.markdown("---")
        
        # 2. 全場一括：大荒れベスト5
        st.markdown("#### 🔴 波乱注意！大荒れレース（全場総合トップ5）")
        df_wild = df_all_res.sort_values("manshu_rate", ascending=False).head(5)
        for _, row in df_wild.iterrows():
            venue_name_only = row['venue'].split('_')[1]
            btn_label = f"【{venue_name_only} {int(row['rno'])}R】 万舟率: {int(row['manshu_rate'])}% ➔"
            if st.button(btn_label, key=f"all_btn_wd_{row['venue']}_{row['rno']}"):
                st.session_state["target_venue"] = row['venue']
                st.session_state["target_rno"] = str(int(row['rno']))
                st.session_state["current_tab"] = "🔍 自分で分析・予想" # 👈 🔥強制ワープ
                st.session_state["auto_search"] = True
                st.session_state["toast_msg"] = f"🏃‍♂️ AI厳選から 【{venue_name_only} {int(row['rno'])}R】 をロードしました！"
                st.rerun()

        st.markdown("---")
        
        # 3. 全場一括：企画通りベスト5
        st.markdown("#### 🔵 軸固定！企画通り狙いレース（全場総合トップ5）")
        
        kikaku_rows = []
        for _, row in df_all_res.iterrows():
            if row["rno"] <= 8: 
                valid_slots = kikaku_master.get(str(row["jcd"]), {}).get("kikaku_slots", [])
                if int(row["rno"]) in valid_slots:
                    kikaku_rows.append(row)
        
        if not kikaku_rows:
            st.caption("※本日の1〜8レース内に、条件に合う明らかなシード企画枠はありません。")
        else:
            df_kikaku = pd.DataFrame(kikaku_rows).sort_values("in_escape_rate", ascending=False).head(5)
            for _, row in df_kikaku.iterrows():
                venue_name_only = row['venue'].split('_')[1]
                btn_label = f"【{venue_name_only} {int(row['rno'])}R】 イン逃げ率: {int(row['in_escape_rate'])}% ➔"
                if st.button(btn_label, key=f"all_btn_kk_{row['venue']}_{row['rno']}"):
                    st.session_state["target_venue"] = row['venue']
                    st.session_state["target_rno"] = str(int(row['rno']))
                    st.session_state["current_tab"] = "🔍 自分で分析・予想" # 👈 🔥強制ワープ
                    st.session_state["auto_search"] = True
                    st.session_state["toast_msg"] = f"🏃‍♂️ AI厳選から 【{venue_name_only} {int(row['rno'])}R】 をロードしました！"
                    st.rerun()
