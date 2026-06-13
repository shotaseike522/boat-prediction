import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import os

def safe_float(val):
    if not val: return 0.0
    val = str(val).replace('%', '').strip()
    if val in ['-', '- -', '']: return 0.0
    try: return float(val)
    except: return 0.0

def update_master():
    master_file = 'racer_master.csv'
    today_file = 'real_time_出走表.csv'
    
    if not os.path.exists(today_file):
        print("⚠️ 本日の出走表CSVが見つかりません。")
        return

    # 💡 あなたのアイデアにより、通信ゼロで今日の選手を瞬時に抽出！
    df_today = pd.read_csv(today_file)
    today_tobans = set()
    for i in range(1, 7):
        col = f"登番_{i}"
        if col in df_today.columns:
            vals = df_today[col].dropna().tolist()
            for v in vals:
                try:
                    # CSVから読み込んだ数値(例: 4565.0)を、綺麗な4桁の文字列("4565")に直す
                    t = str(int(float(v)))
                    if len(t) == 4:
                        today_tobans.add(t)
                except:
                    pass
    
    today_tobans = list(today_tobans)
    
    if not today_tobans:
        print("⚠️ 本日の出場選手が取得できませんでした。")
        return

    # 既存マスタの読み込み
    if os.path.exists(master_file):
        df_master = pd.read_csv(master_file)
        df_master['登録番号'] = df_master['登録番号'].astype(str)
    else:
        df_master = pd.DataFrame(columns=['登録番号', '更新日'])

    existing_tobans = set(df_master['登録番号'].tolist())
    
    # ターゲットの選定（優先1: 新人、優先2: 更新日が古い人）
    new_racers = [t for t in today_tobans if t not in existing_tobans]
    
    if not df_master.empty:
        df_master['更新日'] = pd.to_datetime(df_master['更新日'], errors='coerce')
        old_racers_df = df_master[df_master['登録番号'].isin(today_tobans)].sort_values('更新日')
        old_racers = old_racers_df['登録番号'].astype(str).tolist()
    else:
        old_racers = []

    # 合計50名をピックアップ
    target_racers = (new_racers + old_racers)[:50]
    print(f"🔄 本日の更新ターゲット: 新規 {len(new_racers[:50])}名 / 既存更新 {len(target_racers) - len(new_racers[:50])}名")

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    updated_data = []
    
    for toban in target_racers:
        time.sleep(1)
        url = f"https://www.boatrace.jp/owpc/pc/data/racersearch/course?toban={toban}"
        racer_info = {"登録番号": toban, "更新日": datetime.now().strftime("%Y-%m-%d")}
        for course in range(1, 7):
            racer_info[f"{course}コース_進入率"] = 0.0
            racer_info[f"{course}コース_1着率"] = 0.0
            racer_info[f"{course}コース_2着率"] = 0.0
            racer_info[f"{course}コース_3着率"] = 0.0
            racer_info[f"{course}コース_平均ST"] = 0.00
            racer_info[f"{course}コース_ST順"] = 0.0

        try:
            res = session.get(url, timeout=10)
            if res.url != url or "データが存在しないので" in res.text:
                updated_data.append(racer_info)
                continue
                
            soup = BeautifulSoup(res.content, "html.parser")
            tables = soup.find_all("div", class_="table1")
            
            if tables and len(tables) >= 4:
                labels = tables[0].find_all("span", class_="table1_progress2Label")
                for i in range(min(6, len(labels))): racer_info[f"{i+1}コース_進入率"] = safe_float(labels[i].text)

                labels = tables[1].find_all("span", class_="table1_progress2Label")
                for i in range(min(6, len(labels))):
                    bars = tables[1].find_all("tr")[i+1].find_all("span", class_="is-progress")
                    if len(bars) >= 1: racer_info[f"{i+1}コース_1着率"] = safe_float(bars[0]['style'].split(':')[1])
                    if len(bars) >= 2: racer_info[f"{i+1}コース_2着率"] = safe_float(bars[1]['style'].split(':')[1])
                    if len(bars) >= 3: racer_info[f"{i+1}コース_3着率"] = safe_float(bars[2]['style'].split(':')[1])

                labels = tables[2].find_all("span", class_="table1_progress2Label")
                for i in range(min(6, len(labels))): racer_info[f"{i+1}コース_平均ST"] = safe_float(labels[i].text)

                labels = tables[3].find_all("span", class_="table1_progress2Label")
                for i in range(min(6, len(labels))): racer_info[f"{i+1}コース_ST順"] = safe_float(labels[i].text)

        except:
            pass
        
        updated_data.append(racer_info)

    # マスタの更新と保存
    df_new = pd.DataFrame(updated_data)
    if not df_master.empty:
        df_combined = pd.concat([df_new, df_master]).drop_duplicates(subset=['登録番号'], keep='first')
    else:
        df_combined = df_new

    df_combined.to_csv(master_file, index=False, encoding='utf-8-sig')
    print(f"🏁 選手マスタの更新完了！ (総収録選手: {len(df_combined)}名)")

if __name__ == "__main__":
    update_master()
