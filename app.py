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

# --- 💡 新機能：マトリックス形式（ズレ修正 ＆ 「全選択」機能） ---
st.markdown("### 🎯 あなたの予想（フォーメーション）")
st.caption("※入力しなくても類似レースの検索は可能です")

# 🛠️ 画面のデザインを完璧に整えるカスタムCSS
st.markdown("""
<style>
/* チェックボックスの余白を完全になくし、文字を非表示にする（中央寄せのため） */
.stCheckbox > label {
    padding-left: 0 !important;
}
.stCheckbox > div[data-testid="stMarkdownContainer"] {
    display: none; /* ラベルを非表示 */
}

/* 行ごとの上下余白を狭くし、補助線（下線）を引く */
div[data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid #dddddd;
    padding-top: 4px !important;
    padding-bottom: 4px !important;
    align-items: center; /* 垂直方向の中央揃え */
}

/* ヘッダー行のスタイル（中央揃え） */
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
    height: 30px; /* 高さを統一 */
    line-height: 30px; /* 文字を垂直中央に */
    border-radius: 4px;
    width: 90%;
    margin: 0 auto;
}

/* チェックボックス（.stCheckbox）の高さをバッジと揃え、中央に寄せる */
.stCheckbox {
    display: flex;
    justify-content: center;
    height: 30px;
    align-items: center;
}
</style>
""", unsafe_allow_html=True)

# テレボート公式のカラー配色の定義
boat_styles = {
    1: "background-color: #ffffff; color: #000000; border: 1px solid #aaaaaa;", # 1: 白
    2: "background-color: #000000; color: #ffffff;",                          # 2: 黒
    3: "background-color: #e02020; color: #ffffff;",                          # 3: 赤
    4: "background-color: #0055b8; color: #ffffff;",                          # 4: 青
    5: "background-color: #fbd100; color: #000000;",                          # 5: 黄
    6: "background-color: #00a040; color: #ffffff;",                          # 6: 緑
    "全": "background-color: #cccccc; color: #333333; font-size: 14px; padding: 2px 0;" # 全: 灰色
}

# --- 動的なチェックボックス状態の管理（セッション状態） ---
# 初期化
if 'pred_1_states' not in st.session_state:
    st.session_state['pred_1_states'] = {i: False for i in range(1, 7)}
if 'all_1_state' not in st.session_state:
    st.session_state['all_1_state'] = False

if 'pred_2_states' not in st.session_state:
    st.session_state['pred_2_states'] = {i: False for i in range(1, 7)}
if 'all_2_state' not in st.session_state:
    st.session_state['all_2_state'] = False

if 'pred_3_states' not in st.session_state:
    st.session_state['pred_3_states'] = {i: False for i in range(1, 7)}
if 'all_3_state' not in st.session_state:
    st.session_state['all_3_state'] = False

# コールバック関数 (号艇チェックボックス用)
def update_all_checkbox(pos):
    # 対応する着順の1〜6号艇のチェック状態を取得
    states = st.session_state[f'pred_{pos}_states']
    # すべてチェックされているか確認し、「全」チェックボックスの状態を更新
    st.session_state[f'all_{pos}_state'] = all(states.values())

# コールバック関数 (全チェックボックス用)
def update_boat_checkboxes(pos):
    # 「全」チェックボックスの新しい状態を取得
    new_state = st.session_state[f'all_{pos}_state']
    # 対応する着順の1〜6号艇すべてに同じ状態を適用
    for i in range(1, 7):
        st.session_state[f'pred_{pos}_states'][i] = new_state

# --- 予想フォーメーション表の表示 ---
pred_1 = []
pred_2 = []
pred_3 = []

# ヘッダー行（横軸：着順）
# 比率を [1.2, 1, 1, 1] にすることで全体の縦ラインを完璧に揃えます
head_cols = st.columns([1.2, 1, 1, 1])
head_cols[0].markdown("<div class='matrix-header'>号艇</div>", unsafe_allow_html=True)
head_cols[1].markdown("<div class='matrix-header'>1着</div>", unsafe_allow_html=True)
head_cols[2].markdown("<div class='matrix-header'>2着</div>", unsafe_allow_html=True)
head_cols[3].markdown("<div class='matrix-header'>3着</div>", unsafe_allow_html=True)

# 縦軸：1〜6号艇のループ
for i in range(1, 7):
    row_cols = st.columns([1.2, 1, 1, 1])
    
    # 公式カラーを適用した数字バッジを出力
    style = boat_styles[i]
    row_cols[0].markdown(f"<div class='boat-badge' style='{style}'>{i}<style>
/* チェックボックスの余白を完全になくし、文字を非表示にする（中央寄せのため） */
.stCheckbox > label {
    padding-left: 0 !important;
}
.stCheckbox > div[data-testid="stMarkdownContainer"] {
    display: none; /* ラベルを非表示 */
}

/* 行ごとの上下余白を狭くし、補助線（下線）を引く */
div[data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid #dddddd;
    padding-top: 4px !important;
    padding-bottom: 4px !important;
    align-items: center; /* 垂直方向の中央揃え */
}

/* ヘッダー行のスタイル（中央揃え） */
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
    height: 30px; /* 高さを統一 */
    line-height: 30px; /* 文字を垂直中央に */
    border-radius: 4px;
    width: 90%;
    margin: 0 auto;
}

/* チェックボックス（.stCheckbox）の高さをバッジと揃え、中央に寄せる */
.stCheckbox {
    display: flex;
    justify-content: center;
    height: 30px;
    align-items: center;
}
</style>
