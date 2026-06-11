import streamlit as st
import pandas as pd
import numpy as np
import os
import itertools
import matplotlib.pyplot as plt
import json
from datetime import datetime
import pytz

# --- 画面設定 ---
st.set_page_config(page_title="競艇 類似レース予想 AI", layout="centered")

# --- 120通りの出目マスタ ---
boats = [1, 2, 3, 4, 5, 6]
all_combos = list(itertools.permutations(boats, 3))
combo_strings = [f"{c[0]}-{c[1]}-{c[2]}" for c in all_combos]

# --- 24競艇場のマスタデータ ---
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

# --- ⏰ 日付の自動チェック ---
jst = pytz.timezone('Asia/Tokyo')
today_jst = datetime.now(jst).strftime("%Y%m%d")
display_today = datetime.now(jst).strftime("%m/%d")

is_data_today = False
if os.path.exists("real_time_出走表.csv"):
    try:
        df_check = pd.read_csv("real_time_出走表.csv")
        if "date" in df_check.columns and str(df_check["date"].iloc[0]) == today_jst:
            is_data_today = True
    except:
        pass

# --- 🔄 セッション状態初期化 ---
if "target_venue" not in st.session_state: st.session_state["target_venue"] = "" 
if "target_rno" not in st.session_state: st.session_state["target_rno"] = ""
if "auto_search" not in st.session_state: st.session_state["auto_search"] = False
if "reset_counter" not in st.session_state: st.session_state["reset_counter"] = 0
if "clicked_btn_key" not in st.session_state: st.session_state["clicked_btn_key"] = None

# --- 🧠 【重要】AIマスタ型の動的判定ロジック ---
def get_pattern_column_name(rel_rates, available_columns):
    """今日の勝率からAIクラスタの型名を逆算推測し、マスタの列を特定する"""
    max_boat = np.argmax(rel_rates) + 1
    strongs = [i+1 for i, val in enumerate(rel_rates) if val >= 0.5]
    weaks = [i+1 for i, val in enumerate(rel_rates) if val <= -0.8]
    
    if max_boat == 1 and rel_rates[0] > 0.8:
        guess = "1強_6号艇ド弱型" if 6 in weaks else "1号艇一強_王道型"
    elif rel_rates[0] < -0.1 and (2 in strongs or 3 in strongs or 4 in strongs):
        guess = "イン凹み_中枠強襲型"
    elif max_boat in [4, 5, 6]:
        guess = "4カド一撃型" if max_boat == 4 else f"{max_boat}号艇エース_展開型"
    elif len(weaks) > 0 and max_boat != 1:
        guess = f"{weaks[0]}号艇ド弱_壁抜け型"
    else:
        guess = f"{max_boat}号艇軸_標準型"
        
    for col in available_columns:
        if guess in col: return col
    for col in available_columns:
        if f"{max_boat}号艇" in col: return col
    return available_columns[0] if available_columns else None

# --- ⚡ ベイズ期待確率の計算エンジン ---
def calculate_true_probabilities(rel_rates, similar_100_df, venue_full_name):
    # 1. マスタ（事前確率）の読み込み
    master_path = f"{venue_full_name}_パターン別確率マスタ.csv"
    base_probs = {combo: 100/120 for combo in combo_strings} # 基準フラット
    
    if os.path.exists(master_path):
        df_master = pd.read_csv(master_path, index_col=0)
        col_name = get_pattern_column_name(rel_rates, df_master.columns.tolist())
        if col_name:
            base_probs = df_master[col_name].to_dict()

    # 2. 類似100レース（尤度）の集計
    def make_result_str(row): return f"{int(row['r1'])}-{int(row['r2'])}-{int(row['r3'])}"
    similar_100_df['3連単'] = similar_100_df.apply(make_result_str, axis=1)
    obs_counts = similar_100_df['3連単'].value_counts().to_dict()
    total_obs = len(similar_100_df)
    
    # 3. ベイズ更新（スムージング付き）と正規化
    raw_expected = {}
    for combo in combo_strings:
        # 0回でも0.5%の可能性を持たせる（ラプラススムージング）
        obs_val = max((obs_counts.get(combo, 0) / total_obs * 100), 0.5) if total_obs > 0 else 0.5
        base_val = base_probs.get(combo, 0.5)
        raw_expected[combo] = obs_val * base_val
        
    total_raw = sum(raw_expected.values())
    true_probs = {k: (v / total_raw * 100) for k, v in raw_expected.items()}
    
    # 高い順にソートして返す
    return dict(sorted(true_probs.items(), key=lambda item: item[1], reverse=True))

# --- ⚡ AI厳選用：一括計算キャッシュロジック ---
@st.cache_data(ttl=1800) 
def generate_ai_ranking_cached(date_str):
    if not os.path.exists("real_time_出走表.csv"): return None
        
    df_today = pd.read_csv("real_time_出走表.csv")
    all_race_results = []
    
    for _, row in df_today.iterrows():
        jcd_str = f"{int(row['jcd']):02d}"
        venue_full_name = venues_map.get(jcd_str)
        if not venue_full_name or not os.path.exists(f"{venue_full_name}.csv"): continue
        
        rel_rates = [row['相対勝率_1'], row['相対勝率_2'], row['相対勝率_3'], row['相対勝率_4'], row['相対勝率_5'], row['相対勝率_6']]
        
        # 類似100レース抽出
        df_past = pd.read_csv(f"{venue_full_name}.csv", encoding='utf-8-sig')
        past_patterns = df_past[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values
        distances = np.linalg.norm(past_patterns - np.array(rel_rates), axis=1)
        df_past['tmp_dist'] = distances
        similar_100 = df_past.sort_values('tmp_dist').head(100).copy()
        similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)
        
        honmei_count = (similar_100['p'] <= 1000).sum()
        manshu_count = (similar_100['p'] >= 10000).sum()
        
        # 真の確率計算
        true_probs = calculate_true_probabilities(rel_rates, similar_100, venue_full_name)
        
        # 企画通りの確率合算（1番手➔2番手追従）
        sorted_rel = sorted({i+1: rel_rates[i] for i in range(6)}.items(), key=lambda x: x[1], reverse=True)
        top1, top2 = str(sorted_rel[0][0]), str(sorted_rel[1][0])
        
        kikaku_prob_sum = 0
        for combo, prob in true_probs.items():
            c = combo.split('-')
            if c[0] == top1 and (c[1] == top2 or c[2] == top2):
                kikaku_prob_sum += prob
        
        all_race_results.append({
            "venue": venue_full_name, "jcd": jcd_str, "rno": int(row['r']),
            "honmei_rate": honmei_count, "manshu_rate": manshu_count,
            "kikaku_prob": kikaku_prob_sum
        })
        
    return pd.DataFrame(all_race_results) if all_race_results else None

# ====================================================
# 📱 画面レイアウト
# ====================================================
tab_search, tab_ai = st.tabs(["🔍 自分で分析・予想", "🤖 本日のAI厳選"])

# ====================================================
# 🔍 タブ1: 自分で分析・予想
# ====================================================
with tab_search:
    st.markdown("### 1. レース情報の指定")
    if st.session_state["auto_search"] or st.session_state.get("clicked_btn_key"):
        st.caption(f"💡 現在選択中：{st.session_state['target_venue'].split('_')[1]} {st.session_state['target_rno']}R")

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
    st.markdown("### 🎯 あなたの予想（フォーメーション）")
    st.caption("※入力しなくても分析は可能です")

    rid = st.session_state["reset_counter"]
    c1, c2, c3 = st.columns(3)
    b_opts = [1, 2, 3, 4, 5, 6]

    with c1:
        all_1 = st.toggle("【全】", key=f"m_all_1_{rid}")
        pred_1 = b_opts if all_1 else st.multiselect("1着", b_opts, placeholder="選択..", label_visibility="collapsed", key=f"sel_1_{rid}")
    with c2:
        all_2 = st.toggle("【全】", key=f"m_all_2_{rid}")
        pred_2 = b_opts if all_2 else st.multiselect("2着", b_opts, placeholder="選択..", label_visibility="collapsed", key=f"sel_2_{rid}")
    with c3:
        all_3 = st.toggle("【全】", key=f"m_all_3_{rid}")
        pred_3 = b_opts if all_3 else st.multiselect("3着", b_opts, placeholder="選択..", label_visibility="collapsed", key=f"key_3_{rid}")

    if st.button("❌ 予想入力をすべてクリアする", use_container_width=True):
        st.session_state["reset_counter"] += 1
        st.rerun()

    st.markdown("---")
    search_triggered = st.button("レースを分析する 🔍", use_container_width=True)
    if search_triggered: st.session_state["clicked_btn_key"] = None
    if st.session_state["auto_search"]:
        search_triggered = True
        st.session_state["auto_search"] = False 

    if search_triggered:
        if os.path.exists("real_time_出走表.csv"):
            df_today = pd.read_csv("real_time_出走表.csv")
            df_target = df_today[(df_today['jcd'] == int(jcd_str)) & (df_today['r'] == int(rno_str))]
            file_path = f"{selected_venue}.csv"
            
            if df_target.empty:
                st.warning(f"⚠️ **【レース情報無し】** 本日、{selected_venue.split('_')[1]}競艇場の第 {rno_str} レースの当日データは存在しません。")
            else:
                rel_rates = [df_target.iloc[0][f'相対勝率_{i}'] for i in range(1, 7)]
                
                df_past = pd.read_csv(file_path, encoding='utf-8-sig')
                past_patterns = df_past[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values
                df_past['距離'] = np.linalg.norm(past_patterns - np.array(rel_rates), axis=1)
                similar_100 = df_past.sort_values('距離').head(100).copy()
                similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)

                # 🎯 真の期待確率を計算
                true_probs = calculate_true_probabilities(rel_rates, similar_100, selected_venue)

                # ① フォーメーション予想結果
                if pred_1 and pred_2 and pred_3:
                    st.markdown("### 🎯 あなたのフォーメーション評価")
                    raw_combos = list(itertools.product(pred_1, pred_2, pred_3))
                    valid_combos = [f"{c[0]}-{c[1]}-{c[2]}" for c in raw_combos if len(set(c)) == 3]
                    
                    if valid_combos:
                        my_prob_sum = sum([true_probs.get(c, 0) for c in valid_combos])
                        st.info(f"あなたの買い目（計**{len(valid_combos)}点**）の真の合算期待確率: **{my_prob_sum:.1f}%**")
                        
                        my_probs = {c: true_probs.get(c, 0) for c in valid_combos}
                        top_my_probs = dict(sorted(my_probs.items(), key=lambda x: x[1], reverse=True)[:5])
                        st.markdown("#### 🌟 予想内の期待値ベスト5")
                        for i, (combo, prob) in enumerate(top_my_probs.items()):
                            if prob > 0: st.success(f"**第{i+1}位：【 {combo} 】** （期待確率: {prob:.1f}%）")
                    st.markdown("---")

                # ② 全体の真の確率ベスト5
                st.markdown("## 🏆 真の期待確率ベスト5 (AI正規化済)")
                top5_overall = list(true_probs.items())[:5]
                for i, (combo, prob) in enumerate(top5_overall):
                    st.markdown(f"**第{i+1}位: 【 {combo} 】** （確率: {prob:.1f}%）")
                st.markdown("---")

                # ③ 配当分布グラフ
                st.markdown("### 📈 類似100レースの配当分布（荒れ度チェック）")
                bins = [0, 1000, 3000, 5000, 10000, 30000, 1000000] 
                labels = ['~1.0k', '1.0k~3k', '3k~5k', '5k~10k', '10k~30k', '30k~']
                similar_100['配当帯'] = pd.cut(similar_100['p'], bins=bins, labels=labels, right=False)
                dist = similar_100['配当帯'].value_counts().reindex(labels).fillna(0)
                
                fig, ax = plt.subplots(figsize=(6, 3.2), facecolor='none')
                ax.set_facecolor('none')
                ax.bar(dist.index, dist.values, color='#1f77b4', alpha=0.8, edgecolor='#114466')
                ax.set_ylim(0, 100)
                ax.tick_params(colors='#888888', labelsize=9)
                for spine in ax.spines.values(): spine.set_color('#444444')
                st.pyplot(fig, clear_figure=True)
                st.markdown("---")

                # 📊 ハイブリッド型・ステータス判定
                r_int = int(rno_str)
                honmei_pct = (similar_100['p'] <= 1000).sum()  
                manshu_pct = (similar_100['p'] >= 10000).sum()
                
                sorted_rel = sorted({i+1: rel_rates[i] for i in range(6)}.items(), key=lambda x: x[1], reverse=True)
                top1, top2 = str(sorted_rel[0][0]), str(sorted_rel[1][0])
                
                kikaku_prob_sum = sum([p for c, p in true_probs.items() if c.startswith(top1) and (c.split('-')[1] == top2 or c.split('-')[2] == top2)])

                if r_int <= 8 and kikaku_prob_sum >= 25.0:
                    status_text = f"🔵 企画通り（『1番強い{top1}号艇➔2番目{top2}号艇追従』の確率が{kikaku_prob_sum:.1f}%に達する狙い打ちレース）"
                elif manshu_pct >= 20:
                    status_text = f"🔴 大穴注意（過去100回中{manshu_pct}回も万舟が出ている波乱番組。手広く買うか見送り推奨）"
                elif honmei_pct >= 30: 
                    status_text = f"🟢 ド安定（過去100回中{honmei_pct}回が1000円以下の本命決着。上位数点に絞って厚め勝負）"
                else:
                    status_text = "⚪ 波乱含み / 🟡 普通（極端な傾向なし。直前のオッズと展示を見て判断）"
                    
                st.markdown(f"#### 📊 レースの性質： {status_text}")
        else: st.error("当日出走表ファイルが配置されていません。")

# ====================================================
# 🤖 タブ2: 本日のAI厳選
# ====================================================
with tab_ai:
    st.markdown(f"### 🌟 本日 ({display_today}) のAI厳選 各ベスト5")
    
    if not is_data_today:
        st.warning("⚠️ **【本日のデータは現在更新待ちです】**")
    else:
        df_all_res = generate_ai_ranking_cached(today_jst)
        if df_all_res is not None:
            
            # 1. 企画通り ベスト5
            st.markdown("#### 🔵 企画通り・軸固定レース ベスト5")
            st.caption("1〜8R限定。AI計算の『真の期待確率』において、1強➔2強の決着確率が最も高いレース。")
            df_kikaku = df_all_res[df_all_res["rno"] <= 8].sort_values("kikaku_prob", ascending=False).head(5)
            for _, row in df_kikaku.iterrows():
                v_name = row['venue'].split('_')[1]
                btn_label = f"【{v_name} {int(row['rno'])}R】 軸追従期待確率: {row['kikaku_prob']:.1f}% ➔"
                btn_id = f"kk_{row['venue']}_{row['rno']}"
                if st.button(btn_label, key=f"all_btn_{btn_id}"):
                    st.session_state.update({"target_venue": row['venue'], "target_rno": str(int(row['rno'])), "auto_search": True, "clicked_btn_key": btn_id})
                    st.rerun()
                if st.session_state["clicked_btn_key"] == btn_id: st.success("✅ セット完了！『🔍 自分で分析・予想』タブを開いてください。")
            st.markdown("---")
            
            # 2. 大穴注意 ベスト5
            st.markdown("#### 🔴 大荒れ・波乱注意レース ベスト5")
            st.caption("配当実績において、過去に万舟（1万円以上）が飛び出した回数が最も多いレース。")
            df_wild = df_all_res.sort_values("manshu_rate", ascending=False).head(5)
            for _, row in df_wild.iterrows():
                v_name = row['venue'].split('_')[1]
                btn_label = f"【{v_name} {int(row['rno'])}R】 万舟発生回数: {int(row['manshu_rate'])}回/100 ➔"
                btn_id = f"wd_{row['venue']}_{row['rno']}"
                if st.button(btn_label, key=f"all_btn_{btn_id}"):
                    st.session_state.update({"target_venue": row['venue'], "target_rno": str(int(row['rno'])), "auto_search": True, "clicked_btn_key": btn_id})
                    st.rerun()
                if st.session_state["clicked_btn_key"] == btn_id: st.success("✅ セット完了！『🔍 自分で分析・予想』タブを開いてください。")
            st.markdown("---")

            # 3. ド安定 ベスト5
            st.markdown("#### 🟢 ガチガチ・本命レース ベスト5")
            st.caption("配当実績において、過去に1,000円以下の極小配当で決まった回数が最も多いレース。")
            df_stable = df_all_res.sort_values("honmei_rate", ascending=False).head(5)
            for _, row in df_stable.iterrows():
                v_name = row['venue'].split('_')[1]
                btn_label = f"【{v_name} {int(row['rno'])}R】 1000円以下回数: {int(row['honmei_rate'])}回/100 ➔"
                btn_id = f"st_{row['venue']}_{row['rno']}"
                if st.button(btn_label, key=f"all_btn_{btn_id}"):
                    st.session_state.update({"target_venue": row['venue'], "target_rno": str(int(row['rno'])), "auto_search": True, "clicked_btn_key": btn_id})
                    st.rerun()
                if st.session_state["clicked_btn_key"] == btn_id: st.success("✅ セット完了！『🔍 自分で分析・予想』タブを開いてください。")
