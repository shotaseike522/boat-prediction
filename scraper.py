import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import pytz
import os

def fetch_today_all_races():
    # 日本時間（JST）を取得
    jst = pytz.timezone('Asia/Tokyo')
    now_jst = datetime.now(jst)
    hd_str = now_jst.strftime("%Y%m%d")
    print(f"--- [JST {now_jst.strftime('%Y-%m-%d %H:%M:%S')}] 当日データ取得を開始します ---")

    # 既存のデータがあるか確認（リトライ時に無駄な再取得を防ぐ）
    if os.path.exists("real_time_出走表.csv"):
        try:
            df_exist = pd.read_csv("real_time_出走表.csv")
            if "date" in df_exist.columns and str(df_exist["date"].iloc[0]) == hd_str and len(df_exist) > 10:
                print("🎉 すでに本日のデータが正常に取得済みです。処理をスキップします。")
                return True
        except:
            pass

    # 開催一覧ページから、本日開催している競艇場コードだけを事前に引っこ抜く
    index_url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={hd_str}"
    active_jcds = []
    
    place_dict = {
        "桐生":1,"戸田":2,"江戸川":3,"平和島":4,"多摩川":5,"浜名湖":6,
        "蒲郡":7,"常滑":8,"津":9,"三国":10,"びわこ":11,"住之江":12,
        "尼崎":13,"鳴門":14,"丸亀":15,"児島":16,"宮島":17,"徳山":18,
        "下関":19,"若松":20,"芦屋":21,"福岡":22,"唐津":23,"大村":24
    }
    
    try:
        res = requests.get(index_url, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")
        td_list = soup.find_all("td", class_="is-arrow1 is-fBold is-fs15")
        
        for td in td_list:
            img_tag = td.find("img", alt=True)
            if img_tag and img_tag["alt"] in place_dict:
                active_jcds.append(place_dict[img_tag["alt"]])
                
        print(f"📋 本日の開催競艇場を検知しました (計 {len(active_jcds)} 場): {active_jcds}")
    except Exception as e:
        print(f"⚠️ 開催一覧ページの取得に失敗しました。全場スキャンに切り替えます: {e}")
        # 万が一一覧ページが落ちていた場合は、セーフティとして24場すべてを対象にする
        active_jcds = list(range(1, 25))

    all_rows = []
    
    # 🎯 抽出された「本日開催している競艇場」のみを対象にループを回す
    for jcd_int in active_jcds:
        jcd_str = f"{jcd_int:02d}"
        print(f" └ 競艇場コード [{jcd_str}] の全12レースを解析中...")
        
        for rno in range(1, 13):
            url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd_str}&hd={hd_str}"
            try:
                res = requests.get(url, timeout=10)
                soup = BeautifulSoup(res.content, "html.parser")
                
                # 💡【改良ロジック】6艇それぞれの<tr>ブロックを直接探す
                # 選手の枠ごとに <tbody class="is-fs12"> で区切られているのを利用する
                tbodies = soup.find_all("tbody", class_="is-fs12")
                
                # 6艇分のデータが見つからない場合はスキップ（非開催など）
                if len(tbodies) != 6:
                    continue
                    
                rates = []
                
                for tbody in tbodies:
                    # その選手のブロックの最初の行 (<tr>) を取得
                    first_tr = tbody.find("tr")
                    # 最初の行の中にある列 (<td>) をすべて取得
                    tds = first_tr.find_all("td", recursive=False)
                    
                    # HTML構造上、全国勝率は必ず「左から5番目（インデックス4）」の<td>に入る
                    if len(tds) > 4:
                        # <br>を改行としてテキストを抽出し、1行目（勝率）だけを取り出す
                        txt = tds[4].get_text(separator="\n").strip().split('\n')[0]
                        
                        # 💡 セーフティネット: "-.--" や空文字が来たら 0.00 に置換する
                        if txt == "-.--" or not txt:
                            rates.append(0.00)
                        else:
                            try:
                                rates.append(float(txt))
                            except ValueError:
                                rates.append(0.00)
                    else:
                        rates.append(0.00)
                
                # 6艇分の勝率が正常に取得できなかった場合はスキップ
                if len(rates) != 6:
                    continue
                        
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
                print(f"   ⚠️ [{jcd_str}] {rno}R の取得中にエラーが発生しました: {e}")
                continue

    # CSVとして保存
    if len(all_rows) > 0:
        df_new = pd.DataFrame(all_rows)
        df_new.to_csv("real_time_出走表.csv", index=False, encoding='utf-8-sig')
        print(f"💾 本日の出走表（計 {len(df_new)} レース分）を「real_time_出走表.csv」に保存しました！")
        return True
    else:
        print("❌ 有効な出走表データが1つも取得できませんでした。")
        return False

if __name__ == "__main__":
    fetch_today_all_races()
