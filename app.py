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

# --- 💡 マトリックス形式フォーメーション入力 ---
st.markdown("### 🎯 あなたの予想（フォーメーション）")
st.caption("※入力しなくても類似レースの検索は可能です")

# 🛠️ ズレを完全に防ぎ、デザインを整えるカスタムCSS
st.markdown("""
<style>
/* チェックボックスの無駄な余白を削り、ラベルテキストを消す */
.stCheckbox > label {
    padding-left: 0 !important;
}
.stCheckbox > div[data-testid="stMarkdownContainer"] {
    display: none !important;
}
/* ヘッダー行のスタイル */
.matrix-header {
    text-align: center;
    font-weight: bold;
    font-size: 15px;
    color: #333333;
}
/* テレボート風・号艇バッジのスタイル */
.boat-badge {
    display: block;
    text-align: center;
    font-weight: bold;
    font-size: 16px;
    height: 30px;
    line-height: 30px;
    border-radius: 4px;
    width: 90%;
    margin: 0 auto;
}
/* チェックボックスを各列の完全な中央に配置する */
.stCheckbox {
    display: flex;
    justify-content: center;
    height: 30px;
    align-items: center;
}
</style>
""", unsafe_allow_html=True)

# テレボート公式カラー定義
boat_styles = {
    1: "background-color: #ffffff; color: #000000; border: 1px solid #aaaaaa;", 
    2: "background-color: #000000; color: #ffffff;",                          
    3: "background-color: #e02020; color: #ffffff;",                          
    4: "background-color: #0055b8; color: #ffffff;",                          
    5: "background-color: #fbd100; color: #000000;",                          
    6: "background-color: #00a040; color: #ffffff;",                          
    "全": "background-color: #777777; color: #ffffff; font-size: 14px;"
}

# --- 🔄 セッション状態の初期化と双方向連動ロジック ---
for p in [1, 2, 3]:
    for i in range(1, 7):
        if f"boat_{p}_{i}" not in st.session_state:
            st.session_state[f"boat_{p}_{i}"] = False
    if f"all_{p}" not in st.session_state:
        st.session_state[f"all_{p}"] = False

# 「全」が押された時の処理
def click_all(p):
    new_val = st.session_state[f"all_{p}"]
    for i in range(1, 7):
        st.session_state[f"boat_{p}_{i}"] = new_val

# 各号艇が押された時の処理
def click_boat(p):
    st.session_state[f"all_{p}"] = all(st.session_state[f"boat_{p}_{i}"] for i in range(1, 7))

# --- マトリックス表のレンダリング ---
# ヘッダー（着順）
head_cols = st.columns([1.2, 1, 1, 1])
head_cols[0].markdown("<div class='matrix-header'>号艇</div>", unsafe_allow_html=True)
head_cols[1].markdown("<div class='matrix-header'>1着</div>", unsafe_allow_html=True)
head_cols[2].markdown("<div class='matrix-header'>2着</div>", unsafe_allow_html=True)
head_cols[3].markdown("<div class='matrix-header'>3着</div>", unsafe_allow_html=True)
st.markdown("<hr style='margin: 4px 0; border: 0; border-top: 1px solid #bbbbbb;'>", unsafe_allow_html=True)

# 1〜6号艇の行ループ
for i in range(1, 7):
    row_cols = st.columns([1.2, 1, 1, 1])
    row_cols[0].markdown(f"<div class='boat-badge' style='{boat_styles[i]}'>{i}</div>", unsafe_allow_html=True)
    
    row_cols[1].checkbox("", key=f"boat_1_{i}", on_change=click_boat, args=(1,))
    row_cols[2].checkbox("", key=f"boat_2_{i}", on_change=click_boat, args=(2,))
    row_cols[3].checkbox("", key=f"boat_3_{i}", on_change=click_boat, args=(3,))
    st.markdown("<hr style='margin: 4px 0; border: 0; border-top: 1px solid #eeeeee;'>", unsafe_allow_html=True)

# 「全」選択の行
row_all_cols = st.columns([1.2, 1, 1, 1])
row_all_cols[0].markdown(f"<div class='boat-badge' style='{boat_styles['全']}'>全</div>", unsafe_allow_html=True)
row_all_cols[1].checkbox("", key="all_1", on_change=click_all, args=(1,))
row_all_cols[2].checkbox("", key="all_2", on_change=click_all, args=(2,))
row_all_cols[3].checkbox("", key="all_3", on_change=click_all, args=(3,))
st.markdown("<hr style='margin: 4px 0; border: 0; border-top: 1px solid #bbbbbb;'>", unsafe_allow_html=True)

# チェックが入っている号艇のリストを回収
pred_1 = [i for i in range(1, 7) if st.session_state[f"boat_1_{i}"]]
pred_2 = [i for i in range(1, 7) if st.session_state[f"boat_2_{i}"]]
pred_3 = [i for i in range(1, 7) if st.session_state[f"boat_3_{i}"]]


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
