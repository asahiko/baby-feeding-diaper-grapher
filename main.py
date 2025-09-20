import pandas as pd
import matplotlib.pyplot as plt
import datetime

# サンプルデータ
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
            if "○" in token:
                t = parse_time(token.replace("○", ""))
                if t: events.append((t, None))
            elif "L" in token and "R" in token:
                tstr = token[:5]
                t = parse_time(tstr)
                # L15R20 形式 → 分数合計
                rest = token[5:]
                mins = 0
                if "L" in rest:
                    mins += int(rest.split("R")[0][1:])
                if "R" in rest:
                    mins += int(rest.split("R")[1])
                if t: events.append((t, mins))
        elif kind in ["搾乳","ミルク"]:
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
            if t: events.append((t, token[5:] if len(token)>5 else "○"))
    return events

# ---------- 可視化 ----------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10,8))

colors = {"直母":"tab:blue","搾乳":"tab:green","ミルク":"tab:orange","尿":"tab:purple","便":"tab:brown"}

# eventplot
for i, row in df.iterrows():
    date = row["date"]
    for kind in colors.keys():
        events = parse_events(row.get(kind,""), kind)
        times = [t.hour + t.minute/60 for t,v in events if t]
        if times:
            ax1.eventplot(times, lineoffsets=i, colors=colors[kind], linelengths=0.8)
ax1.set_yticks(range(len(df)))
ax1.set_yticklabels(df["date"])
ax1.set_xlim(0,24)
ax1.set_xlabel("Hour of day")
ax1.set_ylabel("Date")
ax1.set_title("授乳・おむつイベント")

# 授乳量積み上げ棒
feeding_totals = []
for i, row in df.iterrows():
    date = row["date"]
    totals = {"直母":0,"搾乳":0,"ミルク":0}
    for kind in totals.keys():
        events = parse_events(row.get(kind,""), kind)
        for t,v in events:
            if v: totals[kind]+=v
    feeding_totals.append([date,totals["直母"],totals["搾乳"],totals["ミルク"]])

feeding_df = pd.DataFrame(feeding_totals, columns=["date","直母","搾乳","ミルク"])
feeding_df.set_index("date").plot(
    kind="bar", stacked=True, ax=ax2, color=[colors["直母"],colors["搾乳"],colors["ミルク"]]
)
ax2.set_ylabel("授乳量 (ml or min)")
ax2.set_title("1日ごとの授乳量")

plt.tight_layout()
plt.show()
