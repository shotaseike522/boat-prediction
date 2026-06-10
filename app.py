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

venues = [
    "01_桐生", "02_戸田", "03_江戸川", "04_平和島", "05_多摩川", "06_浜名湖",
    "07_蒲郡", "08_常滑", "09_津", "10_三国", "11_びわこ", "12_住之江",
    "13_尼崎", "14_鳴門", "15_丸亀", "16_児島", "17_宮島", "18_徳山",
    "19_下関", "20_若松", "21_芦屋", "22_福岡", "23_唐津", "24_大村"
]

# --- 🔄 セッション状態（ページ跨ぎのデータ保持）の初期化 ---
if "target_venue" not in st.session_state:
    st.session_state["target_venue"] = venues[8] # デフォルトは「津」
if "target_rno" not in st.session_state:
    st.session_state["target_rno"] = "1"
if "auto_search" not in st.session_state:
    st.session_state["auto_search"] = False

# 日付表示用の動的ラベル作成（本日と明日のみ）
today_dt = datetime.now()
tomorrow_dt = today_dt + timedelta(days=1)
date_options = {
    f"当日 ({today_dt.strftime('%m/%d')})": today_dt,
    f"翌日 ({tomorrow_dt.strftime('%m/%d')})": tomorrow_dt
}

if "target_date_label" not in st.session_state:
    st.session_state["target_date_label"] = list(date_options.keys())[0]

# --- 📡 データ取得ロジック（高速キャッシュ ＆ フォールバック対応） ---
@st.cache_data(ttl=3600) # 1時間キャッシュ（深夜の自動取得がなくても、誰か1人が押せばその日は一瞬で動く）
def fetch_race_data_cached(hd_str, jcd_str, rno_str):
    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno_str}&jcd={jcd_str}&hd={hd_str}"
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.content, "html.parser")
        syouritu_elements = soup.find_all(class_="is-lineH2")
        
        if not syouritu_elements or len(syouritu_elements) < 27:
            return None, None
            
        rates = []
        target_indices = [1, 6, 11, 16, 21, 26] 
        for i in target_indices:
            txt = syouritu_elements[i].text.split('\n')[0]
            rates.append(float(txt))
                
        mean_rate = sum(rates) / 6
        relative_rates = [round(r - mean_rate, 3) for r in rates]
        return rates, relative_rates
    except:
        return None, None

# 12レース分を裏で一括計算する関数（AI厳選用）
def analyze_all_12_races(hd_str, jcd_str, venue_file):
    if not os.path.exists(venue_file):
        return None
    
    df_past = pd.read_csv(venue_file, encoding='utf-8-sig')
    past_patterns = df_past[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values
    
    results = []
    for rno in range(1, 13):
        _, rel_rates = fetch_race_data_cached(hd_str, jcd_str, str(rno))
        if rel_rates is None:
            continue
            
        # 類似100レースの抽出
        distances = np.linalg.norm(past_patterns - np.array(rel_rates), axis=1)
        df_past['distance'] = distances
        similar_100 = df_past.sort_values('distance').head(100).copy()
        
        similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)
        
        # 指標の計算
        honmei_count = (similar_100['p'] < 1500).sum()
        manshu_count = (similar_100['p'] >= 10000).sum()
        in_escape_count = (similar_100['r1'] == 1.0).sum()
        
        results.append({
            "rno": rno,
            "honmei_rate": honmei_count,  # 100個中なのでそのまま%
            "manshu_rate": manshu_count,
            "in_escape_rate": in_escape_count
        })
    return results


# ====================================================
# 📱 画面レイアウト（2タブ構成）
# ====================================================
st.title("🚤 競艇 類似レース予想 AI")

tab_ai, tab_search = st.tabs(["🤖 本日のAI厳選", "🔍 自分で分析・予想"])

# ====================================================
# 🤖 タブ1: 本日のAI厳選
# ====================================================
with tab_ai:
    st.markdown("### 🌟 AIがデータから見つけた本日の勝負レース")
    st.caption("その日の12レースを裏で一括分析し、データの偏りが大きい上位を推薦します。")
    
    col_ai1, col_ai2 = st.columns(2)
    with col_ai1:
        ai_date_label = st.selectbox("📅 日付の選択", list(date_options.keys()), key="ai_date_sel")
        ai_hd = date_options[ai_date_label].strftime("%Y%m%d")
    with col_ai2:
        ai_venue = st.selectbox("📌 競艇場の選択", venues, key="ai_venue_sel")
        ai_jcd = ai_venue.split("_")[0]
        
    venue_file = f"{ai_venue}.csv"
    
    if st.button("AI厳選ランキングを生成 ⚙️", use_container_width=True):
        with st.spinner("本日（明日）の全レースをAIが解析中...（約10秒）"):
            summary_results = analyze_all_12_races(ai_hd, ai_jcd, venue_file)
            
        if not summary_results:
            st.error("出走表データがまだ公開されていないか、過去データファイルが見つかりません。")
            st.caption("※翌日の出走表は前日の19時〜20時頃に公開されます。")
        else:
            df_res = pd.DataFrame(summary_results)
            
            # ① ド安定ベスト5 (本命確率順)
            st.markdown("#### 🟢 鉄板！ド安定レース（上位）")
            df_stable = df_res.sort_values("honmei_rate", ascending=False).head(5)
            for _, row in df_stable.iterrows():
                if st.button(f"第 {int(row['rno'])} レース （本命率: {int(row['honmei_rate'])}%） を分析する ➔", key=f"btn_st_{row['rno']}"):
                    st.session_state["target_venue"] = ai_venue
                    st.session_state["target_rno"] = str(int(row['rno']))
                    st.session_state["target_date_label"] = ai_date_label
                    st.session_state["auto_search"] = True
                    st.rerun()
                    
            st.markdown("---")
            
            # ② 大荒れベスト5 (万舟確率順)
            st.markdown("#### 🔴 波乱注意！大荒れレース（上位）")
            df_wild = df_res.sort_values("manshu_rate", ascending=False).head(5)
            for _, row in df_wild.iterrows():
                if st.button(f"第 {int(row['rno'])} レース （万舟率: {int(row['manshu_rate'])}%） を分析する ➔", key=f"btn_wd_{row['rno']}"):
                    st.session_state["target_venue"] = ai_venue
                    st.session_state["target_rno"] = str(int(row['rno']))
                    st.session_state["target_date_label"] = ai_date_label
                    st.session_state["auto_search"] = True
                    st.rerun()

            st.markdown("---")
            
            # ③ 企画通りベスト5 (1-8R限定 ＆ マスタ合致)
            st.markdown("#### 🔵 軸固定！企画通り狙いレース")
            valid_kikaku_slots = kikaku_master.get(ai_jcd, {}).get("kikaku_slots", [])
            
            # 1-8R ＆ マスタに存在するレース番号でフィルター
            df_kikaku = df_res[(df_res["rno"] <= 8) & (df_res["rno"].isin(valid_kikaku_slots))]
            
            if df_kikaku.empty:
                st.caption("※本日（明日）の1〜8レース内に、条件に合う明らかなシード企画枠はありません。")
            else:
                df_kikaku = df_kikaku.sort_values("in_escape_rate", ascending=False).head(5)
                for _, row in df_kikaku.iterrows():
                    if st.button(f"第 {int(row['rno'])} レース （イン逃げ率: {int(row['in_escape_rate'])}%） を分析する ➔", key=f"btn_kk_{row['rno']}"):
                        st.session_state["target_venue"] = ai_venue
                        st.session_state["target_rno"] = str(int(row['rno']))
                        st.session_state["target_date_label"] = ai_date_label
                        st.session_state["auto_search"] = True
                        st.rerun()


# ====================================================
# 🔍 タブ2: 自分で分析・予想
# ====================================================
with tab_search:
    st.markdown("### 1. レース情報の指定")
    col1, col2, col3 = st.columns(3)

    with col1:
        # AI厳選からの連動を受ける
        v_idx = venues.index(st.session_state["target_venue"]) if st.session_state["target_venue"] in venues else 8
        selected_venue = st.selectbox("📌 競艇場", venues, index=v_idx)
        jcd_str = selected_venue.split("_")[0] 

    with col2:
        d_label = st.selectbox("📅 日付", list(date_options.keys()), index=list(date_options.keys()).index(st.session_state["target_date_label"]))
        hd_str = date_options[d_label].strftime("%Y%m%d")

    with col3:
        r_options = [str(i) for i in range(1, 13)]
        r_idx = r_options.index(st.session_state["target_rno"]) if st.session_state["target_rno"] in r_options else 0
        rno_str = st.selectbox("🚤 レース", r_options, index=r_idx)

    st.markdown("---")

    # --- 💡 スマホ特化型フォーメーション入力 ---
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

    # 検索が実行されたかどうかのトリガー
    search_triggered = st.button("類似レースを検索して分析する 🔍", use_container_width=True)
    
    # AI厳選からの自動検索ジャンプ対応
    if st.session_state["auto_search"]:
        search_triggered = True
        st.session_state["auto_search"] = False # 即座にリセット

    if search_triggered:
        with st.spinner("公式データと照合中..."):
            raw_rates, rel_rates = fetch_race_data_cached(hd_str, jcd_str, rno_str)
            
        if raw_rates is None:
            st.error("指定されたレースの出走表データが取得できませんでした。時間をおいて再度お試しください。")
        else:
            file_path = f"{selected_venue}.csv"
            if os.path.exists(file_path):
                df = pd.read_csv(file_path, encoding='utf-8-sig')

                user_pattern = np.array(rel_rates)
                past_patterns = df[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values

                df['距離'] = np.linalg.norm(past_patterns - user_pattern, axis=1)
                similar_100 = df.sort_values('distance' if 'distance' in df.columns else '距離').head(100).copy()

                def make_result_str(row):
                    return f"{int(row['r1'])}-{int(row['r2'])}-{int(row['r3'])}"
                similar_100['3連単'] = similar_100.apply(make_result_str, axis=1)
                similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)

                # ----------------====================================
                # ① あなたのフォーメーション予想結果（一番上に配置 ＆ 金額非表示）
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
                # ⚙️ 💡 AI自動ステータス判定（ド安定・大荒れ・企画通り）の表示
                # ----------------====================================
                # マスタデータに基づく判定
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
                # ③ 配当分布グラフ（金額帯・文字化け完全回避）
                # ----------------====================================
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
                st.error(f"過去データファイルが見つかりません: {file_path}")
