import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import itertools

# --- 画面設定 ---
st.set_page_config(page_title="競艇 類似レース予想", layout="centered")
st.title("🚤 競艇 類似レース予想ツール")
st.write("公式サイトから出走表を自動取得し、過去のパターンから最も似ている100レースの確率を出します。")

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

# --- 💡 新機能：マトリックス形式（テレボート風）フォーメーション入力 ---
st.markdown("### 🎯 あなたの予想（フォーメーション）")
st.caption("※入力しなくても類似レースの検索は可能です")

pred_1 = []
pred_2 = []
pred_3 = []

# ヘッダー行（1〜6の号艇番号）
head_cols = st.columns([1, 1, 1, 1, 1, 1, 1])
for i in range(1, 7):
    head_cols[i].markdown(f"<div style='text-align: center'><b>{i}</b></div>", unsafe_allow_html=True)

# 1着の行
row1_cols = st.columns([1, 1, 1, 1, 1, 1, 1])
row1_cols[0].markdown("<b>1着</b>", unsafe_allow_html=True)
for i in range(1, 7):
    # チェックボックスを配置し、チェックされたらリストに号艇番号を追加
    if row1_cols[i].checkbox("", key=f"1着_{i}"):
        pred_1.append(i)

# 2着の行
row2_cols = st.columns([1, 1, 1, 1, 1, 1, 1])
row2_cols[0].markdown("<b>2着</b>", unsafe_allow_html=True)
for i in range(1, 7):
    if row2_cols[i].checkbox("", key=f"2着_{i}"):
        pred_2.append(i)

# 3着の行
row3_cols = st.columns([1, 1, 1, 1, 1, 1, 1])
row3_cols[0].markdown("<b>3着</b>", unsafe_allow_html=True)
for i in range(1, 7):
    if row3_cols[i].checkbox("", key=f"3着_{i}"):
        pred_3.append(i)

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
if st.button("出走表を取得して類似100レースを検索 🔍", use_container_width=True):
    
    with st.spinner("公式サイトからデータを取得中..."):
        raw_rates, rel_rates = fetch_boat_data(hd_str, jcd_str, rno_str)
        
    if raw_rates is None:
        st.error("指定されたレースの出走表データが取得できませんでした。")
    else:
        st.success("データ取得成功！")
        
        st.markdown("#### 📥 取得した勝率データ")
        cols = st.columns(6)
        for i in range(6):
            cols[i].metric(label=f"{i+1}号艇", value=f"{raw_rates[i]}", delta=f"{rel_rates[i]} (相対)")
        st.markdown("---")

        # --- 類似レース検索処理 ---
        file_path = f"{selected_venue}.csv"
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, encoding='utf-8-sig')

            user_pattern = np.array(rel_rates)
            past_patterns = df[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values

            df['距離'] = np.linalg.norm(past_patterns - user_pattern, axis=1)
            similar_100 = df.sort_values('距離').head(100)

            # 📈 配当分布
            st.markdown("## 📈 類似100レースの配当分布（荒れやすさ）")
            similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)
            bins = [0, 1500, 3000, 5000, 10000, 30000, 1000000]
            labels = ['本命(~1.5千円)', '中穴(1.5~3千円)', '中穴(3~5千円)', '大穴(5千~1万円)', '万舟(1万~3万円)', '超万舟(3万円~)']
            similar_100['配当帯'] = pd.cut(similar_100['p'], bins=bins, labels=labels, right=False)
            
            dist = similar_100['配当帯'].value_counts(sort=False)
            st.bar_chart(dist)
            st.markdown("---")

            def make_result_str(row):
                return f"{int(row['r1'])}-{int(row['r2'])}-{int(row['r3'])}"
            similar_100['3連単'] = similar_100.apply(make_result_str, axis=1)

            # 🏆 ベスト3
            st.markdown("## 🏆 頻出着順ベスト3")
            top3 = similar_100['3連単'].value_counts().head(3)
            
            for i, (result, count) in enumerate(top3.items()):
                avg_payout = similar_100[similar_100['3連単'] == result]['p'].mean()
                st.success(f"**第{i+1}位: 【 {result} 】** 出現率: **{count}%** （平均配当: {int(avg_payout)}円）")

            # --- 🎯 答え合わせ（マトリックス入力の判定） ---
            if pred_1 and pred_2 and pred_3:
                st.markdown("---")
                st.markdown("### 🎯 あなたのフォーメーション予想結果")
                
                raw_combos = list(itertools.product(pred_1, pred_2, pred_3))
                # 1-1-2などの重複を除外
                valid_combos = [f"{c[0]}-{c[1]}-{c[2]}" for c in raw_combos if len(set(c)) == 3]
                
                if valid_combos:
                    my_hits = similar_100[similar_100['3連単'].isin(valid_combos)]
                    my_count = len(my_hits)
                    
                    if my_count > 0:
                        my_avg_payout = my_hits['p'].mean()
                        st.info(f"あなたの予想（計**{len(valid_combos)}点**）の合算出現率: **{my_count}%**")
                        st.info(f"的中した場合の平均配当: **{int(my_avg_payout)}円**")
                        
                        best_hit = my_hits['3連単'].value_counts().head(1)
                        st.caption(f"※ちなみに、あなたの予想内で最も出やすかったのは 【 {best_hit.index[0]} 】 でした。")
                    else:
                        st.warning(f"あなたの予想（計{len(valid_combos)}点）は、今回の類似100レースでは1度も発生していません。来れば大穴です！")
                else:
                    st.error("有効な買い目がありません（同じ号艇が重複して選択されています）。")

        else:
            st.error(f"データファイルが見つかりません: {file_path}")
