import os
import argparse
import datetime
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
import japanize_matplotlib
from matplotlib.lines import Line2D

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
            "stool": ["09:00 13:00△", "09:30× 16:00"],
            "weight": [4.5, 4.7]
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
    m = re.match(r'(\d{1,2}:?\d{0,2})([LR]\d{1,2})?([LR]\d{1,2})?(.*)', s)
    if m is not None:
        breast_time = parse_time(m.group(1))
        if m.group(3) is not None:
            breast_length = int(m.group(2)[1:]) + int(m.group(3)[1:])
        elif m.group(2) is not None:
            breast_length = int(m.group(2)[1:])
        else:
            breast_length = None
        note = m.group(4).strip() if m.group(4).strip() else None
        return breast_time, breast_length, note
    return None, None, None

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

def plot_with_matplotlib(breast_df, pumped_df, formula_df, urine_df, stool_df, count_df, weight_df):
    colors = {"直母":"#ed8e89","搾乳":"#003864","ミルク":"#6a8fc3","尿":"#ffd457","便":"#81612f"}
    
    fig = plt.figure(figsize=(14, 10))
    gs = gridspec.GridSpec(4, 4, figure=fig)
    ax_eventplot = fig.add_subplot(gs[0:2, :])
    ax_eventcount = fig.add_subplot(gs[2:4, 0:2])
    ax_milk = fig.add_subplot(gs[2:4, 2])
    ax_weight = fig.add_subplot(gs[2:4, 3])
    
    # eventplot
    all_dates = sorted(set(breast_df['date']).union(set(pumped_df['date'])).union(set(formula_df['date'])).union(set(urine_df['date'])).union(set(stool_df['date'])))
    date_to_index = {date: idx for idx, date in enumerate(all_dates)}
    
    for df, kind in [(breast_df, "直母"), (pumped_df, "搾乳"), (formula_df, "ミルク"), (urine_df, "尿"), (stool_df, "便")]:
        for i, row in df.iterrows():
            date_idx = date_to_index[row['date']]
            time = row['time']
            if pd.notna(time):
                hour = time.hour + time.minute / 60
                ax_eventplot.eventplot([hour], 
                                       lineoffsets=date_idx, 
                                       colors=colors[kind], 
                                       linelengths=0.9, 
                                       linewidths=2,
                                       orientation='vertical')
    
    legend_elements = [
        Line2D([0], [0], color=colors["直母"], lw=4, label='直接母乳'),
        Line2D([0], [0], color=colors["搾乳"], lw=4, label='搾母乳'),
        Line2D([0], [0], color=colors["ミルク"], lw=4, label='粉ミルク'),
        Line2D([0], [0], color=colors["尿"], lw=4, label='おむつ（小）'),
        Line2D([0], [0], color=colors["便"], lw=4, label='おむつ（大）'),
    ]
    ax_eventplot.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(0.95, 0.5), title="凡例", framealpha=1)
    ax_eventplot.set_title("授乳・おむつ替えのタイムライン")
    ax_eventplot.set_xticks(range(len(all_dates)))
    # 2日おきにラベル、それ以外は空文字
    xticklabels = [
        date.strftime("%m/%d") if i % 2 == 0 else ""
        for i, date in enumerate(all_dates)
    ]
    ax_eventplot.set_xticklabels(xticklabels)
    plt.setp(ax_eventplot.get_xticklabels(), rotation=90, ha="right")
    ax_eventplot.set_yticks([0, 6, 12, 18, 24])
    ax_eventplot.set_yticks(range(0, 24), minor=True)
    ax_eventplot.set_ylim(0, 24)
    ax_eventplot.set_ylabel("時")
    ax_eventplot.set_xlabel("日付")
    ax_eventplot.invert_yaxis()

    # 日ごとの集計
    feeding_totals = []
    direct_totals = []
    for date in all_dates:
        pumped_total = pumped_df[pumped_df['date'] == date]['amount'].sum() if not pumped_df[pumped_df['date'] == date].empty else 0
        formula_total = formula_df[formula_df['date'] == date]['amount'].sum() if not formula_df[formula_df['date'] == date].empty else 0
        breast_total = breast_df[breast_df['date'] == date]['length'].sum() if not breast_df[breast_df['date'] == date].empty else 0
        feeding_totals.append([date, pumped_total, formula_total])
        direct_totals.append([date, breast_total])
    ax_eventcount.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax_eventcount.set_title("24時間合計")
    ax_eventcount.set_xlabel("日付")
    ax_eventcount.set_ylabel("回数")
    plt.setp(ax_eventcount.get_xticklabels(), rotation=90, ha="right")

    # 各お世話の回数
    # 授乳系を積み上げグラフに、
    markers = ['o', 'o', 'o', 'd', 'd']
    columns = ['breast', 'pumped', 'formula', 'urine', 'stool']

    for i, col in enumerate(columns):
        ax_eventcount.plot(
            count_df['date'],
            count_df[col],
            marker=markers[i],
            color=colors[["直母", "搾乳", "ミルク", "尿", "便"][i]],
            label=["直接母乳", "搾母乳", "粉ミルク", "おむつ交換（尿）", "おむつ交換（便）"][i]
        )

    # 搾乳 + ミルク (積み上げ棒)
    feeding_df = pd.DataFrame(feeding_totals, columns=["date","搾乳","ミルク"])
    # x軸を日付型でbar描画
    ax_milk.bar(feeding_df["date"], feeding_df["搾乳"], color=colors["搾乳"], label="搾母乳")
    ax_milk.bar(feeding_df["date"], feeding_df["ミルク"], bottom=feeding_df["搾乳"], color=colors["ミルク"], label="粉ミルク")
    ax_milk.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    plt.setp(ax_milk.get_xticklabels(), rotation=90, ha="right")
    ax_milk.set_xlabel("日付")
    ax_milk.set_ylabel("授乳量 (ml)")
    ax_milk.set_title("授乳量（直母含まず）")
    ax_milk.legend()

    # 体重グラフ
    if not weight_df.empty:
        ax_weight.plot(weight_df['date'], weight_df['weight'], marker='o', color='gray')
    else:
        ax_weight.text(0.5, 0.5, "体重データなし", horizontalalignment='center', verticalalignment='center', transform=ax_weight.transAxes)
    ax_weight.set_title("体重")
    ax_weight.set_xlabel("日付")
    ax_weight.set_ylabel("体重 (kg)")
    ax_weight.set_ylim(0, None)
    ax_weight.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    plt.setp(ax_weight.get_xticklabels(), rotation=90, ha="right")

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
    count_records = []
    weight_records = []
    
    for row in df.itertuples():
        if pd.notna(row.breast):
            tokens = str(row.breast).split()
            for token in tokens:
                time, length, note = parse_breast_entry(token)
                if time:
                    rec = {"date": row.date, "time": time, "length": length, "note": note}
                    breast_records.append(rec)
            
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

        if pd.notna(row.urine):
            tokens = str(row.urine).split()
            for token in tokens:
                time, note = parse_diaper_entry(token)
                if time:
                    rec = {"date": row.date, "time": time, "note": note}
                    urine_records.append(rec)

        if pd.notna(row.stool):
            tokens = str(row.stool).split()
            for token in tokens:
                time, note = parse_diaper_entry(token)
                if time:
                    rec = {"date": row.date, "time": time, "note": note}
                    stool_records.append(rec)

        if hasattr(row, "weight") and pd.notna(getattr(row, "weight", None)):
            weight_records.append({"date": row.date, "weight": row.weight})
        
        # 日毎の各お世話の回数の集計
        print(f"=== {row.date} の集計 ===")
        breast_count = len([r for r in breast_records if r['date'] == row.date])
        pumped_count = len([r for r in pumped_records if r['date'] == row.date])
        formula_count = len([r for r in formula_records if r['date'] == row.date])
        urine_count = len([r for r in urine_records if r['date'] == row.date])
        stool_count = len([r for r in stool_records if r['date'] == row.date])
        count_records.append({"date": row.date, "breast": breast_count, "pumped": pumped_count, "formula": formula_count, "urine": urine_count, "stool": stool_count})
        print("")

    breast_df = pd.DataFrame(breast_records)
    pumped_df = pd.DataFrame(pumped_records)
    formula_df = pd.DataFrame(formula_records)
    urine_df = pd.DataFrame(urine_records)
    stool_df = pd.DataFrame(stool_records)
    count_df = pd.DataFrame(count_records)
    weight_df = pd.DataFrame(weight_records)

    # DEBUG: 各記録のDataFrameをprint
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
    print("=== 日ごとのお世話回数 ===")
    print(count_df)

    # ---------- 可視化 ----------
    if args.plotter == "matplotlib":
        plot_with_matplotlib(breast_df, pumped_df, formula_df, urine_df, stool_df, count_df, weight_df)
    elif args.plotter == "plotly":
        print("Plotlyによる可視化は未実装です")
    else:
        print("不明なプロットライブラリ指定")

if __name__ == "__main__":
    args = parse_args()
    main(args)