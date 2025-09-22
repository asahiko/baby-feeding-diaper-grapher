import os
import argparse
import datetime
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import japanize_matplotlib

def parse_args():
    parser = argparse.ArgumentParser(description="授乳・おむつ記録の可視化")
    parser.add_argument("-f", "--file", help="入力ファイル, CSV or Excel (xlsx)")
    parser.add_argument("-p", "--plotter", choices=["matplotlib", "plotly"], default="matplotlib", help="プロットライブラリの選択 (デフォルト: matplotlib)")
    return parser.parse_args()

def load_data(filename: str | None = None):
    if filename is None:
        print("入力ファイルなし、デフォルトデータで例示")
        data = {
            "date": ["2025-09-15", "2025-09-16"],
            "breast": ["08:00L15R20 11:30○", "07:30L20R15"],
            "pumped": ["09:00-60 14:00-40", "10:00-50"],
            "formula": ["12:30-100a 18:30-80", "13:00-120"],
            "urine": ["07:00 10:00 15:30", "08:00 12:00"],
            "stool": ["09:00 13:00△", "09:30× 16:00"]
        }
        df = pd.DataFrame(data)
    else:
        if filename.endswith(".csv"):
            df = pd.read_csv(filename)
        elif filename.endswith(".xlsx"):
            df = pd.read_excel(filename)
        else:
            raise ValueError("対応しているのはCSVかExcelファイルのみです")
            
        if "date" not in df.columns:
            raise ValueError("CSVには 'date' 列が必要です")
        
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df
    
def parse_time(s):
    s = s.strip()
    if not s:
        return None
    # "9" など時だけの簡略表記のとき、15:30とみなす
    if s.isdigit():
        hour = int(s)
        if 0 <= hour < 24:
            return datetime.time(hour, 30)
    # "09:00" 形式
    try:
        return datetime.datetime.strptime(s, "%H:%M").time()
    except:
        pass
    return None
    
def parse_breast_entry(s: str):
    """
    直接母乳の授乳時刻と左右の授乳時間(分)をパースする
    例:
    '8:20L10R10' -> breast_time = 08:20:00, breast_length = 20
    '9' -> breast_time = 09:00:00, breast_length = None
    """
    s = s.strip()
    m = re.match(r'(\d{1,2}:?\d{0,2})([LR]\d{1,2})?([LR]\d{1,2})?', s)
    if m is not None:
        breast_time = parse_time(m.group(1))
        if m.group(3) is not None:
            breast_length = int(m.group(2)[1:]) + int(m.group(3)[1:])
        elif m.group(2) is not None:
            breast_length = int(m.group(2)[1:])
        else:
            breast_length = None
        return breast_time, breast_length
    return None, None

def parse_diaper_entry(s: str):
    """
    おむつ交換の時刻と備考をパースする
    例:
    '09:00△' -> diaper_time = 09:00:00, note = '△'
    '10:30' -> diaper_time = 10:30:00, note = None
    """
    s = s.strip()
    m = re.match(r'(\d{1,2}:?\d{0,2})(.*)', s)
    if m is not None:
        diaper_time = parse_time(m.group(1))
        note = m.group(2).strip() if m.group(2).strip() else None
        return diaper_time, note
    return None, None

def plot_with_matplotlib(breast_df, pumped_df, formula_df, urine_df, stool_df):
    """
    Matplotlibで可視化
    Plot 1: 授乳・おむつイベントのタイムライン
    Plot 2: 日ごとの授乳量 (搾乳 + ミルク)
    Plot 3: 日ごとの直母授乳時間
    """
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10,12))
    colors = {"直母":"forestgreen","搾乳":"turquoise","ミルク":"royalblue","尿":"gold","便":"peru"}

    # eventplot
    all_dates = sorted(set(breast_df['date']).union(set(pumped_df['date'])).union(set(formula_df['date'])).union(set(urine_df['date'])).union(set(stool_df['date'])))
    date_to_index = {date: idx for idx, date in enumerate(all_dates)}
    
    for df, kind in [(breast_df, "直母"), (pumped_df, "搾乳"), (formula_df, "ミルク"), (urine_df, "尿"), (stool_df, "便")]:
        for i, row in df.iterrows():
            date_idx = date_to_index[row['date']]
            time = row['time']
            if pd.notna(time):
                hour = time.hour + time.minute / 60
                ax1.eventplot([hour], lineoffsets=date_idx, colors=colors[kind], linelengths=0.8, orientation='vertical')
    
    ax1.set_xticks(range(len(all_dates)))
    ax1.set_xticklabels([date.strftime("%m/%d") for date in all_dates])
    ax1.set_yticks([0, 6, 12, 18, 24])
    ax1.set_yticks(range(0, 24), minor=True)
    ax1.set_ylim(0, 24)
    ax1.set_ylabel("Hour of day")
    ax1.set_xlabel("Date")
    ax1.set_title("授乳・おむつイベント")
    ax1.invert_yaxis()

    # 日ごとの集計
    feeding_totals = []
    direct_totals = []
    for date in all_dates:
        pumped_total = pumped_df[pumped_df['date'] == date]['amount'].sum() if not pumped_df[pumped_df['date'] == date].empty else 0
        formula_total = formula_df[formula_df['date'] == date]['amount'].sum() if not formula_df[formula_df['date'] == date].empty else 0
        breast_total = breast_df[breast_df['date'] == date]['length'].sum() if not breast_df[breast_df['date'] == date].empty else 0
        feeding_totals.append([date, pumped_total, formula_total])
        direct_totals.append([date, breast_total])

    # 搾乳 + ミルク (積み上げ棒)
    feeding_df = pd.DataFrame(feeding_totals, columns=["date","搾乳","ミルク"])
    feeding_df.set_index("date").plot(
        kind="bar", stacked=True, ax=ax2, color=[colors["搾乳"], colors["ミルク"]]
    )
    ax2.set_xticks(range(len(all_dates)))
    ax2.set_xticklabels([date.strftime("%m/%d") for date in all_dates])
    ax2.set_ylabel("授乳量 (ml)")
    ax2.set_title("1日ごとの授乳量（搾乳・ミルク）")
    ax2.legend(title="授乳方法")

    # 直母 (分)
    direct_df = pd.DataFrame(direct_totals, columns=["date","直母"])
    direct_df.set_index("date").plot(
        kind="bar", ax=ax3, color=colors["直母"]
    )
    ax3.set_xticks(range(len(all_dates)))
    ax3.set_xticklabels([date.strftime("%m/%d") for date in all_dates])
    ax3.set_ylabel("授乳時間 (分)")
    ax3.set_title("1日ごとの直母授乳時間")
    ax3.legend(title="授乳方法")

    plt.tight_layout()
    plt.show()

# ---------- メイン処理 ----------
def main(args):
    if args.file and os.path.exists(args.file):
        df = load_data(args.file)
    else:
        df = load_data()  # サンプルデータ呼出
        
    breast_records = []
    pumped_records = []
    formula_records = []
    urine_records = []
    stool_records = []
    
    for row in df.itertuples():
        if pd.notna(row.breast):
            tokens = str(row.breast).split()
            for token in tokens:
                time, length = parse_breast_entry(token)
                if time:
                    rec = {"date": row.date, "time": time, "length": length}
                    breast_records.append(rec)
                    print(rec)
            
        if pd.notna(row.pumped):
            tokens = str(row.pumped).split()
            for token in tokens:
                m = re.match(r'(\d{1,2}:?\d{0,2})-(\d{1,3})', token.strip())
                if m:
                    time = parse_time(m.group(1))
                    amount = int(m.group(2))
                    if time:
                        rec = {"date": row.date, "time": time, "amount": amount}
                        pumped_records.append(rec)
                        print(rec)

        if pd.notna(row.formula):
            tokens = str(row.formula).split()
            for token in tokens:
                m = re.match(r'(\d{1,2}:?\d{0,2})-(\d{1,3})', token.strip())
                if m:
                    time = parse_time(m.group(1))
                    amount = int(m.group(2))
                    if time:
                        rec = {"date": row.date, "time": time, "amount": amount}
                        formula_records.append(rec)
                        print(rec)

        if pd.notna(row.urine):
            tokens = str(row.urine).split()
            for token in tokens:
                time, note = parse_diaper_entry(token)
                if time:
                    rec = {"date": row.date, "time": time, "note": note}
                    urine_records.append(rec)
                    print(rec)

        if pd.notna(row.stool):
            tokens = str(row.stool).split()
            for token in tokens:
                time, note = parse_diaper_entry(token)
                if time:
                    rec = {"date": row.date, "time": time, "note": note}
                    stool_records.append(rec)
                    print(rec)

    breast_df = pd.DataFrame(breast_records)
    pumped_df = pd.DataFrame(pumped_records)
    formula_df = pd.DataFrame(formula_records)
    urine_df = pd.DataFrame(urine_records)
    stool_df = pd.DataFrame(stool_records)

    # DEBUG: 各記録のDataFrameを作成
    print("=== 直接母乳 ===")
    print(breast_df)
    print("=== 搾乳 ===")
    print(pumped_df)
    print("=== ミルク ===")
    print(formula_df)
    print("=== 尿 ===")
    print(urine_df)
    print("=== 便 ===")
    print(stool_df)

    # ---------- 可視化 ----------
    if args.plotter == "matplotlib":
        plot_with_matplotlib(breast_df, pumped_df, formula_df, urine_df, stool_df)
    elif args.plotter == "plotly":
        print("Plotlyによる可視化は未実装です")
    else:
        print("不明なプロットライブラリ指定")

"""
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10,12))
    colors = {"直母":"tab:blue","搾乳":"tab:green","ミルク":"tab:orange","尿":"tab:purple","便":"tab:brown"}

    # eventplot
    for i, row in df.iterrows():
        for kind in colors.keys():
            events = parse_events(row.get(kind, ""), kind)
            times = [t.hour + t.minute/60 for t,v in events if t]
            if times:
                ax1.eventplot(times, lineoffsets=i, colors=colors[kind], linelengths=0.8)
    ax1.set_yticks(range(len(df)))
    ax1.set_yticklabels(df["date"])
    ax1.set_xlim(0, 24)
    ax1.set_xlabel("Hour of day")
    ax1.set_ylabel("Date")
    ax1.set_title("授乳・おむつイベント")

    # 日ごとの集計
    feeding_totals = []
    direct_totals = []
    for i, row in df.iterrows():
        date = row["date"]
        totals = {"直母":0, "搾乳":0, "ミルク":0}
        for kind in totals.keys():
            events = parse_events(row.get(kind, ""), kind)
            for t,v in events:
                if v:
                    totals[kind] += v
        feeding_totals.append([date, totals["搾乳"], totals["ミルク"]])
        direct_totals.append([date, totals["直母"]])

    # 搾乳 + ミルク (積み上げ棒)
    feeding_df = pd.DataFrame(feeding_totals, columns=["date","搾乳","ミルク"])
    feeding_df.set_index("date").plot(
        kind="bar", stacked=True, ax=ax2, color=[colors["搾乳"], colors["ミルク"]]
    )
    ax2.set_ylabel("授乳量 (ml)")
    ax2.set_title("1日ごとの授乳量（搾乳・ミルク）")

    # 直母 (分)
    direct_df = pd.DataFrame(direct_totals, columns=["date","直母"])
    direct_df.set_index("date").plot(
        kind="bar", ax=ax3, color=colors["直母"]
    )
    ax3.set_ylabel("授乳時間 (分)")
    ax3.set_title("1日ごとの直母授乳時間")

    plt.tight_layout()
    plt.show()
"""

if __name__ == "__main__":
    args = parse_args()
    main(args)