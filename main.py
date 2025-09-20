import pandas as pd
import matplotlib.pyplot as plt
import datetime
import argparse
import os

# ---------- パーサー ----------
def parse_time(s):
    try:
        return datetime.datetime.strptime(s, "%H:%M").time()
    except:
        return None

def parse_events(cell, kind):
    if pd.isna(cell):
        return []
    events = []
    for token in str(cell).split():
        if kind == "直母":
            if "○" in token:  # ○だけ
                t = parse_time(token.replace("○", ""))
                if t: events.append((t, None))
            elif "L" in token and "R" in token:  # LxxRyy
                tstr = token[:5]
                t = parse_time(tstr)
                rest = token[5:]
                mins = 0
                if "L" in rest:
                    try:
                        mins += int(rest.split("R")[0][1:])
                    except:
                        pass
                if "R" in rest:
                    try:
                        mins += int(rest.split("R")[1])
                    except:
                        pass
                if t: events.append((t, mins))
        elif kind in ["搾乳", "ミルク"]:
            try:
                tstr, amt = token.split("-")
                amt = "".join(ch for ch in amt if ch.isdigit())
                t = parse_time(tstr)
                if t: events.append((t, int(amt)))
            except:
                pass
        elif kind == "尿":
            t = parse_time(token)
            if t: events.append((t, None))
        elif kind == "便":
            t = parse_time(token[:5])
            if t: events.append((t, token[5:] if len(token) > 5 else "○"))
    return events

# ---------- メイン処理 ----------
def main():
    parser = argparse.ArgumentParser(description="授乳・おむつ記録の可視化")
    parser.add_argument("--file", help="入力CSVファイル（省略可）")
    args = parser.parse_args()

    if args.file and os.path.exists(args.file):
        df = pd.read_csv(args.file)
        if "date" not in df.columns:
            raise ValueError("CSVには 'date' 列が必要です")
        df["date"] = pd.to_datetime(df["date"]).dt.date
    else:
        # デフォルトデータ
        data = {
            "date": ["2025-09-15", "2025-09-16"],
            "直母": ["08:00L15R20 11:30○", "07:30L20R15"],
            "搾乳": ["09:00-60 14:00-40", "10:00-50"],
            "ミルク": ["12:30-100a 18:30-80", "13:00-120"],
            "尿": ["07:00 10:00 15:30", "08:00 12:00"],
            "便": ["09:00 13:00△", "09:30× 16:00"]
        }
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"]).dt.date

    # ---------- 可視化 ----------
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

if __name__ == "__main__":
    main()