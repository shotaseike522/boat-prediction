import streamlit as st
import pandas as pd
import numpy as np
import os

# --- 画面設定 ---
st.set_page_config(page_title="競艇 類似レース予想", layout="centered")
st.title("🚤 競艇 類似レース予想ツール")
st.write("過去のパターンから、最も似ている100レースを抽出して確率を出します。")

# 競艇場のリスト
venues = [
    "01_桐生", "02_戸田", "03_江戸川", "04_平和島", "05_多摩川", "06_浜名湖",
    "07_蒲郡", "08_常滑", "09_津", "10_三国", "11_びわこ", "12_住之江",
    "13_尼崎", "14_鳴門", "15_丸亀", "16_児島", "17_宮島", "18_徳山",
    "19_下関", "20_若松", "21_芦屋", "22_福岡", "23_唐津", "24_大村"
]

# --- 1. 入力エリア ---
selected_venue = st.selectbox("📌 競艇場を選択してください", venues)

st.markdown("### 📊 各号艇の「相対勝率」を入力")
st.caption("※相対勝率 ＝ その選手の勝率 － 6選手の平均勝率 (例: 1.5, -0.8 など)")

col1, col2, col3 = st.columns(3)
with col1: r1 = st.number_input("1号艇", value=0.0, step=0.1)
with col2: r2 = st.number_input("2号艇", value=0.0, step=0.1)
with col3: r3 = st.number_input("3号艇", value=0.0, step=0.1)

col4, col5, col6 = st.columns(3)
with col4: r4 = st.number_input("4号艇", value=0.0, step=0.1)
with col5: r5 = st.number_input("5号艇", value=0.0, step=0.1)
with col6: r6 = st.number_input("6号艇", value=0.0, step=0.1)

st.markdown("---")
my_pred = st.text_input("🎯 あなたの3連単予想（例: 1-2-3）", "1-2-3")

# --- 2. 検索・計算処理 ---
if st.button("類似100レースを検索 🔍", use_container_width=True):
    file_path = f"{selected_venue}.csv"

    if os.path.exists(file_path):
        df = pd.read_csv(file_path, encoding='utf-8-sig')

        # ユーザー入力パターンと過去データのパターン比較
        user_pattern = np.array([r1, r2, r3, r4, r5, r6])
        past_patterns = df[['相対勝率_1', '相対勝率_2', '相対勝率_3', '相対勝率_4', '相対勝率_5', '相対勝率_6']].values

        # 距離計算と抽出
        df['距離'] = np.linalg.norm(past_patterns - user_pattern, axis=1)
        similar_100 = df.sort_values('距離').head(100)

        # ----------------------------------------------------
        # 📈 新機能：配当分布の可視化（荒れやすさチェック）
        # ----------------------------------------------------
        st.markdown("## 📈 類似100レースの配当分布（荒れやすさ）")
        
        # p列（配当）を数値化
        similar_100['p'] = pd.to_numeric(similar_100['p'], errors='coerce').fillna(0)
        
        # 配当を価格帯ごとに分類
        bins = [0, 1500, 3000, 5000, 10000, 30000, 1000000]
        labels = ['本命(~1.5千円)', '中穴(1.5~3千円)', '中穴(3~5千円)', '大穴(5千~1万円)', '万舟(1万~3万円)', '超万舟(3万円~)']
        similar_100['配当帯'] = pd.cut(similar_100['p'], bins=bins, labels=labels, right=False)
        
        # グラフ描画
        dist = similar_100['配当帯'].value_counts(sort=False)
        st.bar_chart(dist)
        st.caption("※グラフが右（大穴・万舟）に偏っているほど、このパターンは「荒れやすい（波乱含み）」と判断できます。")
        st.markdown("---")

        # ----------------------------------------------------
        # 🏆 ベスト3と自分の予想の答え合わせ
        # ----------------------------------------------------
        def make_result_str(row):
            return f"{int(row['r1'])}-{int(row['r2'])}-{int(row['r3'])}"
        
        similar_100['3連単'] = similar_100.apply(make_result_str, axis=1)

        st.markdown("## 🏆 頻出着順ベスト3")
        top3 = similar_100['3連単'].value_counts().head(3)
        
        for i, (result, count) in enumerate(top3.items()):
            avg_payout = similar_100[similar_100['3連単'] == result]['p'].mean()
            st.success(f"**第{i+1}位: 【 {result} 】** 出現率: **{count}%** （平均配当: {int(avg_payout)}円）")

        st.markdown("### 🎯 あなたの予想の答え合わせ")
        my_count = len(similar_100[similar_100['3連単'] == my_pred])
        
        if my_count > 0:
            my_avg_payout = similar_100[similar_100['3連単'] == my_pred]['p'].mean()
            st.info(f"あなたの予想 **【 {my_pred} 】** の出現率: **{my_count}%** （平均配当: {int(my_avg_payout)}円）")
        else:
            st.warning(f"あなたの予想 **【 {my_pred} 】** は、今回の類似100レースでは1度も発生していません。来れば大穴です！")

    else:
        st.error(f"データファイルが見つかりません: {file_path}")
