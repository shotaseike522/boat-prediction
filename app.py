import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import itertools
import matplotlib.pyplot as plt

# --- 画面設定 ---
st.set_page_config(page_title="競艇 類似レース予想", layout="centered")
st.title("🚤 競艇 類似レース予想ツール")
st.write("過去のパターンから最も似ている100レースの確率を出します。")

venues = [
    "01_桐生", "02_戸田", "03_江戸川", "04_平和島", "05_多摩川", "06_浜名湖",
    "07_蒲郡", "08_常滑", "09_津", "10_三国", "11_びわこ", "12_住之江",
    "13_尼崎", "14_鳴門", "15_丸亀", "16_児島", "17_宮島", "18_徳山",
    "19_下関", "20_若松", "21_芦屋", "22_福岡", "23_唐津", "24_大村"
]

# --- 1. レース情報の入力エリア ---
st.markdown("### 1. レース情報の指定")
col1, col2, col3 = st.columns(3)

with col1:
    target_date = st.date_input("📅 日付")
    hd_str = target_date.strftime("%Y%m%d")

with col2:
    selected_venue = st.selectbox("📌 競艇場", venues)
    jcd_str = selected_venue.split("_")[0] 

with col3:
    rno_str = st.selectbox("🚤 レース番号", [str(i) for i in range(1, 13)])

st.markdown("---")

# --- 💡 スマホ特化型：フォーメーション入力 ---
st.markdown("### 🎯 あなたの予想（フォーメーション）")
st.write("タップして号艇を選ぶか、スイッチで「全通り」にできます。")

# スマホでは自動的に縦に並ぶ安全なレイアウト
c1, c2, c3 = st.columns(3)

boat_options = [1, 2, 3, 4, 5, 6]

with c1:
    st.markdown("#### 🥇 1着")
    all_1 = st.toggle("【全】通りにする", key="all_1")
    sel_1 = st.multiselect("1着の号艇", boat_options, disabled=all_1, label_visibility="collapsed", placeholder="号艇を選択...")
    pred_1 = boat_options if all_1 else sel_1

with c2:
    st.markdown("#### 🥈 2着")
    all_2 = st.toggle("【全】通りにする", key="all_2")
    sel_2 = st.multiselect("2着の号艇", boat_options, disabled=all_2, label_visibility="collapsed", placeholder="号艇を選択...")
    pred_2 = boat_options if all_2 else sel_2

with c3:
    st.markdown("#### 🥉 3着")
    all_3 = st.toggle("【全】通りにする", key="all_3")
    sel_3 = st.multiselect("3着の号艇", boat_options, disabled=all_3, label_visibility="collapsed", placeholder="号艇を選択...")
    pred_3 = boat_options if all_3 else sel_3

st.markdown("---")

# --- 2. データ取得関数 ---
def fetch_boat_data(hd, jcd, rno):
    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd}&hd={hd}"
    res = requests.get(url)
    soup = BeautifulSoup(res.content, "html.parser")
    syouritu_elements = soup.find_all(class_="is-lineH2")
    
    if not syouritu_elements or len(syouritu_elements) < 27:
        return None, None
        
    rates = []
    target_indices = [1, 6, 11, 16, 21, 26] 
    for i in target_indices:
        txt = syouritu_elements[i].text.split('\n')[0]
        try:
            rates.append(float(txt))
        except:
            rates.append(0.0)
            
    mean_rate = sum(rates) / 6
    relative_rates = [round(r - mean_rate, 3) for r in rates]
    return rates, relative_rates

# --- 3. 実行処理 ---
if st.button("予想結果を見る 🔍", use_container_width=True):
    
    with st.spinner("データを取得・計算中..."):
        raw_rates, rel_rates = fetch_boat_data(hd_str, jcd_str, rno_str)
        
    if raw_rates is None:
        st.error("指定されたレースの出走表データが取得できませんでした。")
    else:
        file_path = f"{selected_venue}.csv"
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, encoding='utf-8-sig')

            user_pattern = np.array(rel_rates)
            past_patterns = df[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values

            df['距離'] = np.linalg.norm(past_patterns - user_pattern, axis=1)
            similar_100 = df.sort_values('距離').head(100)

            def make_result_str(row):
                return f"{int(row['r1'])}-{int(row['r2'])}-{int(row['r3'])}"
            similar_100['3連単'] = similar_100.apply(make_result_str, axis=1)

            # ====================================================
            # ① あなたの予想結果 ＆ 予想内ベスト5
            # ====================================================
            st.markdown("## 🎯 あなたの予想結果")
            
            if pred_1 and pred_2 and pred_3:
                raw_combos = list(itertools.product(pred_1, pred_2, pred_3))
                valid_combos = [f"{c[0]}-{c[1]}-{c[2]}" for c in raw_combos if len(set(c)) == 3]
                
                if valid_combos:
                    my_hits = similar_100[similar_100['3連単'].isin(valid_combos)]
                    my_count = len(my_hits)
                    
                    # 合算出現率をドカンと表示
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
            else:
                st.warning("※フォーメーションが入力されていないため、予想結果は計算されませんでした。")

            st.markdown("---")

            # ====================================================
            # ② 全体の頻出着順ベスト3
            # ====================================================
            st.markdown("## 🏆 全体の頻出着順ベスト3")
            top3 = similar_100['3連単'].value_counts().head(3)
            
            for i, (result, count) in enumerate(top3.items()):
                st.markdown(f"**第{i+1}位: 【 {result} 】** （出現率: {count}%）")
                
            st.markdown("---")

            # ====================================================
            # ③ 配当分布グラフ（金額帯）
            # ====================================================
            st.markdown("### 📈 類似100レースの配当分布（荒れやすさ）")
            similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)
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
            st.error(f"データファイルが見つかりません: {file_path}")
