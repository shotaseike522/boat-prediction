import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import itertools
import matplotlib.pyplot as plt
import json

# --- 画面設定 ---
st.set_page_config(page_title="競艇 類似レース予想 AI", layout="centered")

# --- 🧠 企画レースマスタの読み込み ---
if os.path.exists("kikaku_master.json"):
    with open("kikaku_master.json", "r", encoding="utf-8") as f:
        kikaku_master = json.load(f)
else:
    kikaku_master = {}

# 今回テスト対象とする、データが存在する4つの競艇場
venues_pari = {
    "24_大村": "24_大村.csv",
    "09_津": "09_津.csv",
    "04_平和島": "04_平和島.csv",
    "02_戸田": "02_戸田.csv"
}
venues_list = list(venues_pari.keys())

# --- 🔄 セッション状態（ページ跨ぎのデータ保持）の初期化 ---
if "target_venue" not in st.session_state:
    st.session_state["target_venue"] = venues_list[1] # デフォルトは「津」
if "target_rno" not in st.session_state:
    st.session_state["target_rno"] = "1"
if "auto_search" not in st.session_state:
    st.session_state["auto_search"] = False
if "mock_rel_rates" not in st.session_state:
    st.session_state["mock_rel_rates"] = None

# ====================================================
# 📱 画面レイアウト（ご指定通りの2タブ構成に修正）
# ====================================================
tab_search, tab_ai = st.tabs(["🔍 自分で分析・予想", "🤖 本日のAI厳選"])

# ====================================================
# 🔍 タブ1: 自分で分析・予想（昨夜のスマホ特化UIを先頭に）
# ====================================================
with tab_search:
    st.markdown("### 1. レース情報の指定")
    col1, col2 = st.columns(2)

    with col1:
        # AI厳選からの連動を受ける
        v_idx = venues_list.index(st.session_state["target_venue"]) if st.session_state["target_venue"] in venues_list else 1
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
        pred_1 = boat_options if all_1 else st.multiselect("1着", boat_options, placeholder="選択..", label_visibility="collapsed")

    with c2:
        st.markdown("#### 🥈 2着")
        all_2 = st.toggle("【全】", key="m_all_2")
        pred_2 = boat_options if all_2 else st.multiselect("2着", boat_options, placeholder="選択..", label_visibility="collapsed")

    with c3:
        st.markdown("#### 🥉 3着")
        all_3 = st.toggle("【全】", key="m_all_3")
        pred_3 = boat_options if all_3 else st.multiselect("3着", boat_options, placeholder="選択..", label_visibility="collapsed")

    st.markdown("---")

    search_triggered = st.button("類似レースを検索して分析する 🔍", use_container_width=True)
    
    # AI厳選リンクから飛んできた場合の自動トリガー
    if st.session_state["auto_search"]:
        search_triggered = True
        st.session_state["auto_search"] = False 

    if search_triggered:
        file_path = venues_pari[selected_venue]
        if os.path.exists(file_path):
            df_past = pd.read_csv(file_path, encoding='utf-8-sig')

            # 🛠️ フォールバック処理: 公式データが取れない/仮データテスト時は、CSVの該当レースのデータを「今日の出走表」として身代わりに使う
            df_target_r = df_past[df_past['r'] == float(rno_str)]
            if not df_target_r.empty:
                # テスト用に、過去データの適当な1行を「本日の出走表」としてサンプリング
                mock_row = df_target_r.iloc[0]
                rel_rates = [
                    mock_row['相対勝率_1'], mock_row['相対勝率_2'], mock_row['相対勝率_3'],
                    mock_row['相対勝率_4'], mock_row['相対勝率_5'], mock_row['相対勝率_6']
                ]
                
                user_pattern = np.array(rel_rates)
                past_patterns = df_past[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values

                df_past['距離'] = np.linalg.norm(past_patterns - user_pattern, axis=1)
                similar_100 = df_past.sort_values('距離').head(100).copy()

                def make_result_str(row):
                    return f"{int(row['r1'])}-{int(row['r2'])}-{int(row['r3'])}"
                similar_100['3連単'] = similar_100.apply(make_result_str, axis=1)
                similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)

                # ----------------====================================
                # ① あなたのフォーメーション予想結果
                # ----------------====================================
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

                # ----------------====================================
                # AI自動ステータス判定
                # ------------------------------------------------====
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
                st.markdown("---")

                # ----------------====================================
                # ② 全体の頻出着順ベスト3
                # ----------------====================================
                st.markdown("## 🏆 全体の頻出着順ベスト3")
                top3 = similar_100['3連単'].value_counts().head(3)
                for i, (result, count) in enumerate(top3.items()):
                    st.markdown(f"**第{i+1}位: 【 {result} 】** （出現率: {count}%）")
                st.markdown("---")

                # ----------------====================================
                # ③ 配当分布グラフ
                # --------------------------------====================
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
            else:
                st.error("該当レースのテスト用仮データが抽出できませんでした。")
        else:
            st.error(f"過去データファイルが見つかりません: {file_path}")

# ====================================================
# 🤖 タブ2: 本日のAI厳選（全競艇場・全レースから一括ランキング）
# ====================================================
with tab_ai:
    st.markdown("### 🌟 AIがデータから見つけた本日の勝負レース（全場スキャン）")
    st.caption("本日開催されている全競艇場の全12レース（計48レースの仮データ）を裏側で一括解析し、全体のトップ5を推薦します。")
    
    if st.button("全競艇場からAI厳選ランキングを抽出する 🚀", use_container_width=True):
        all_race_results = []
        
        # 手元にある4つのCSV（全48レース）を「今日の全競艇場のレース」と見立ててループ処理
        for venue_name, csv_file in venues_pari.items():
            if not os.path.exists(csv_file):
                continue
            
            df_past = pd.read_csv(csv_file, encoding='utf-8-sig')
            past_patterns = df_past[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values
            jcd = csv_file.split("_")[0]
            
            for rno in range(1, 13):
                # 🛠️ 仮の当日データとして、過去CSVの各レースの1行目を「今日の出走表」として代用（ロード時間0秒）
                df_target_r = df_past[df_past['r'] == float(rno)]
                if df_target_r.empty:
                    continue
                
                mock_row = df_target_r.iloc[0]
                rel_rates = [
                    mock_row['相対勝率_1'], mock_row['相対勝率_2'], mock_row['相対勝率_3'],
                    mock_row['相対勝率_4'], mock_row['相対勝率_5'], mock_row['相対勝率_6']
                ]
                
                # 類似100レースの計算
                distances = np.linalg.norm(past_patterns - np.array(rel_rates), axis=1)
                df_past['tmp_dist'] = distances
                similar_100 = df_past.sort_values('tmp_dist').head(100).copy()
                similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)
                
                # 各指標のカウント
                honmei_count = (similar_100['p'] < 1500).sum()
                manshu_count = (similar_100['p'] >= 10000).sum()
                in_escape_count = (similar_100['r1'] == 1.0).sum()
                
                all_race_results.append({
                    "venue": venue_name,
                    "jcd": jcd,
                    "rno": rno,
                    "honmei_rate": honmei_count,
                    "manshu_rate": manshu_count,
                    "in_escape_rate": in_escape_count
                })
        
        if not all_race_results:
            st.error("解析可能なデータがありません。")
        else:
            df_all_res = pd.DataFrame(all_race_results)
            
            # 1. 全場一括：ド安定ベスト5 (12Rの特選も含む、全体のトップ5)
            st.markdown("#### 🟢 鉄板！ド安定レース（全場総合トップ5）")
            df_stable = df_all_res.sort_values("honmei_rate", ascending=False).head(5)
            for _, row in df_stable.iterrows():
                btn_label = f"【{row['venue'].split('_')[1]} {int(row['rno'])}R】 本命率: {int(row['honmei_rate'])}% ➔"
                if st.button(btn_label, key=f"all_btn_st_{row['venue']}_{row['rno']}"):
                    st.session_state["target_venue"] = row['venue']
                    st.session_state["target_rno"] = str(int(row['rno']))
                    st.session_state["auto_search"] = True
                    st.rerun()
                    
            st.markdown("---")
            
            # 2. 全場一括：大荒れベスト5 (全体の万舟確率トップ5)
            st.markdown("#### 🔴 波乱注意！大荒れレース（全場総合トップ5）")
            df_wild = df_all_res.sort_values("manshu_rate", ascending=False).head(5)
            for _, row in df_wild.iterrows():
                btn_label = f"【{row['venue'].split('_')[1]} {int(row['rno'])}R】 万舟率: {int(row['manshu_rate'])}% ➔"
                if st.button(btn_label, key=f"all_btn_wd_{row['venue']}_{row['rno']}"):
                    st.session_state["target_venue"] = row['venue']
                    st.session_state["target_rno"] = str(int(row['rno']))
                    st.session_state["auto_search"] = True
                    st.rerun()

            st.markdown("---")
            
            # 3. 全場一括：企画通りベスト5 (1-8R限定 ＆ マスタ合致)
            st.markdown("#### 🔵 軸固定！企画通り狙いレース（全場総合トップ5）")
            
            # 1-8Rに絞り、マスタに登録されている企画枠だけにフィルター
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
                    btn_label = f"【{row['venue'].split('_')[1]} {int(row['rno'])}R】 イン逃げ率: {int(row['in_escape_rate'])}% ➔"
                    if st.button(btn_label, key=f"all_btn_kk_{row['venue']}_{row['rno']}"):
                        st.session_state["target_venue"] = row['venue']
                        st.session_state["target_rno"] = str(int(row['rno']))
                        st.session_state["auto_search"] = True
                        st.rerun()
