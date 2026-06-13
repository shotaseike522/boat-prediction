import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import pytz
import os
import random

def get_today_racer_tobans():
    jst = pytz.timezone('Asia/Tokyo')
    hd_str = datetime.now(jst).strftime("%Y%m%d")
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

    index_url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={hd_str}"
    active_jcds = []
    place_dict = {
        "桐生":1,"戸田":2,"江戸川":3,"平和島":4,"多摩川":5,"浜名湖":6,
        "蒲郡":7,"常滑":8,"津":9,"三国":10,"びわこ":11,"住之江":12,
        "尼崎":13,"鳴門":14,"丸亀":15,"児島":16,"宮島":17,"徳山":18,
        "下関":19,"若松":20,"芦屋":21,"福岡":22,"唐津":23,"大村":24
    }
    
    try:
        res = session.get(index_url, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")
        for td in soup.find_all("td", class_="is-arrow1 is-fBold is-fs15"):
            img = td.find("img", alt=True)
            if img and img["alt"] in place_dict:
                active_jcds.append(place_dict[img["alt"]])
    except:
        active_jcds = list(range(1, 25))

    all_tobans = set()
    for jcd_int in active_jcds:
        jcd_str = f"{jcd_int:02d}"
        for rno in range(1, 13):
            time.sleep(0.3)
            url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd_str}&hd={hd_str}"
            try:
                res = session.get(url, timeout=10)
                soup = BeautifulSoup(res.content, "html.parser")
                info_divs = soup.find_all("div", class_="is-fs11")
                found = 0
                for div in info_divs:
                    txt = div.get_text()
                    if "/" in txt:
                        toban = txt.split("/")[0].strip()
                        if toban.isdigit() and len(toban) == 4:
                            all_tobans.add(toban)
                            found += 1
                    if found >= 6: break
            except:
                continue
    return list(all_tobans)

def safe_float(val):
    if not val: return 0.0
    val = str(val).replace('%', '').strip()
    if val in ['-', '- -', '']: return 0.0
    try: return float(val)
    except: return 0.0

def update_master():
    jst = pytz.timezone('Asia/Tokyo')
    master_file = 'racer_master.csv'
    today_file = 'real_time_出走表.csv'
    
    today_tobans = set()
    if os.path.exists(today_file):
        df_today = pd.read_csv(today_file)
        for i in range(1, 7):
            col = f"登番_{i}"
            if col in df_today.columns:
                vals = df_today[col].dropna().tolist()
                for v in vals:
                    try:
                        t = str(int(float(v)))
                        if len(t) == 4: today_tobans.add(t)
                    except: pass
                    
    today_tobans = list(today_tobans)
    if not today_tobans:
        today_tobans = get_today_racer_tobans()
        
    if not today_tobans:
        print("⚠️ 本日の出場選手が取得できませんでした。")
        return

    if os.path.exists(master_file):
        df_master = pd.read_csv(master_file)
        df_master['登録番号'] = df_master['登録番号'].astype(str)
    else:
        df_master = pd.DataFrame(columns=['登録番号', '更新日'])

    existing_tobans = set(df_master['登録番号'].tolist())
    new_racers = [t for t in today_tobans if t not in existing_tobans]
    
    # 7日前の判定も日本時間で行う
    seven_days_ago = pd.to_datetime(datetime.now(jst).date()) - pd.Timedelta(days=7)
    
    if not df_master.empty:
        df_master['更新日'] = pd.to_datetime(df_master['更新日'], errors='coerce')
        condition1 = df_master['登録番号'].isin(today_tobans)
        condition2 = (df_master['更新日'] < seven_days_ago) | (df_master['更新日'].isna())
        
        old_racers_df = df_master[condition1 & condition2].sort_values('更新日')
        old_racers = old_racers_df['登録番号'].astype(str).tolist()
    else:
        old_racers = []

    target_racers = (new_racers + old_racers)[:100]
    print(f"🔄 本日の更新ターゲット: 新規 {len(new_racers[:100])}名 / 既存更新 {len(target_racers) - len(new_racers[:100])}名")

    if not target_racers:
        print("✅ 更新対象の選手はいません。")
        return

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    updated_data = []
    
    for toban in target_racers:
        time.sleep(random.uniform(1.5, 3.5))
        url = f"https://www.boatrace.jp/owpc/pc/data/racersearch/course?toban={toban}"
        # 日付を日本時間でセット
        racer_info = {"登録番号": toban, "更新日": datetime.now(jst).strftime("%Y-%m-%d")}
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
                # 引退・欠番は0で保存し、1週間スキップさせる
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
                
                # 💡 正常にデータが取れた時だけ追加する！
                updated_data.append(racer_info)
            else:
                # ページは開けたがテーブルがない（新人など）
                updated_data.append(racer_info)

        except Exception as e:
            # 💡 【重要】通信エラーやタイムアウトの時は「追加しない（無視する）」
            print(f"⚠️ [{toban}] 通信エラーのためスキップします: {e}")
            continue

    if not updated_data:
        print("⚠️ 有効な更新データがありませんでした。")
        return

    df_new = pd.DataFrame(updated_data)
    if not df_master.empty:
        # 重複を消して新しいデータで上書き
        # ※エラーでスキップされた人は、昔のデータのまま守られます
        df_combined = pd.concat([df_new, df_master]).drop_duplicates(subset=['登録番号'], keep='first')
    else:
        df_combined = df_new

    # 時刻が入っていたら消して綺麗な日付フォーマットに戻す
    df_combined['更新日'] = pd.to_datetime(df_combined['更新日'], errors='coerce').dt.strftime('%Y-%m-%d')
    df_combined.to_csv(master_file, index=False, encoding='utf-8-sig')
    print(f"🏁 選手マスタの更新完了！ (総収録選手: {len(df_combined)}名)")

if __name__ == "__main__":
    update_master()
