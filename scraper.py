import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import pytz
import os

def fetch_today_all_races():
    # 日本時間（JST）を取得
    jst = pytz.timezone('Asia/Tokyo')
    now_jst = datetime.now(jst)
    
    # 💡 運用上の設計：深夜24時（0時）〜午前3時頃までは、JSTの日付は「今日」になるが、
    # 競艇の公式サイトは「その日の朝開催される出走表」として扱うため、そのまま当日日付で検索
    hd_str = now_jst.strftime("%Y%m%d")
    print(f"--- [JST {now_jst.strftime('%Y-%m-%d %H:%M:%S')}] 当日データ取得を開始します ---")

    # 既存のデータがあるか確認（リトライ時に無駄なアクセスを防ぐ）
    if os.path.exists("real_time_出走表.csv"):
        try:
            df_exist = pd.read_csv("real_time_出走表.csv")
            # 1行目が今日の日付で、すでにデータが24場分（ある程度まとまって）存在していればスキップ
            if "date" in df_exist.columns and str(df_exist["date"].iloc[0]) == hd_str and len(df_exist) > 10:
                print("🎉 すでに本日のデータが正常に取得済みです。処理をスキップします。")
                return True
        except:
            pass

    all_rows = []
    
    # 24競艇場をループ
    for jcd_int in range(1, 25):
        jcd_str = f"{jcd_int:02d}"
        
        # 1レース目の出走表をテスト取得して、今日その場でレースが開催されるかチェック
        test_url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno=1&jcd={jcd_str}&hd={hd_str}"
        try:
            res = requests.get(test_url, timeout=10)
            if res.status_code != 200:
                continue
                
            soup = BeautifulSoup(res.content, "html.parser")
            syouritu_elements = soup.find_all(class_="is-lineH2")
            
            # 枠データが存在しない（本日非開催、またはまだ出走表が未公開）場合はスキップ
            if not syouritu_elements or len(syouritu_elements) < 27:
                continue
                
            print(f" └ 競艇場コード [{jcd_str}] の出走表を発見。全12レースを解析中...")
            
            # 開催がある場合、1〜12レースをすべてスキャン
            for rno in range(1, 13):
                url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd_str}&hd={hd_str}"
                res = requests.get(url, timeout=10)
                soup = BeautifulSoup(res.content, "html.parser")
                syouritu_elements = soup.find_all(class_="is-lineH2")
                
                if not syouritu_elements or len(syouritu_elements) < 27:
                    continue
                    
                rates = []
                target_indices = [1, 6, 11, 16, 21, 26] 
                for i in target_indices:
                    txt = syouritu_elements[i].text.split('\n')[0]
                    rates.append(float(txt))
                        
                # 相対勝率（勝率 - 平均値）を計算
                mean_rate = sum(rates) / 6
                rel_rates = [round(r - mean_rate, 3) for r in rates]
                
                all_rows.append({
                    "date": hd_str,
                    "jcd": jcd_int,
                    "r": rno,
                    "相対勝率_1": rel_rates[0],
                    "相対勝率_2": rel_rates[1],
                    "相対勝率_3": rel_rates[2],
                    "相対勝率_4": rel_rates[3],
                    "相対勝率_5": rel_rates[4],
                    "相対勝率_6": rel_rates[5]
                })
        except Exception as e:
            print(f" ⚠️ 競艇場 [{jcd_str}] の取得中にエラーが発生しました（スキップします）: {e}")
            continue

    # 取得したデータをCSVとして保存
    if len(all_rows) > 0:
        df_new = pd.DataFrame(all_rows)
        df_new.to_csv("real_time_出走表.csv", index=False, encoding='utf-8-sig')
        print(f"💾 本日の出走表（計 {len(df_new)} レース分）を「real_time_出走表.csv」に書き込みました！")
        return True
    else:
        print("❌ 本日の開催出走表が公式サイトでまだ1つも公開されていません。")
        return False

if __name__ == "__main__":
    fetch_today_all_races()
