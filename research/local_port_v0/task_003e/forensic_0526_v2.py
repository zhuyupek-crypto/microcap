"""5/26 forensic from existing data: check HL list, prices, trades for 4 stocks."""
import pandas as pd, json, re
from pathlib import Path

T3 = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003")
OUT = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003e")

TARGETS = ["300417.XSHE", "301167.XSHE", "600493.XSHG", "300535.XSHE"]

# 1. JQ portfolio positions for these stocks around 2026-05-25/26
jq_port = pd.read_csv(T3 / "jq_portfolio_normalized.csv")
for s in TARGETS:
    pos = jq_port[(jq_port["normalized_security_code"] == s) &
                  (jq_port["record_date"].isin(["2026-05-25", "2026-05-26"]))]
    print(f"JQ {s}:")
    if len(pos) > 0:
        for _, r in pos.iterrows():
            print(f"  {r['record_date']}: qty={r['position_quantity']} price={r['market_price']} val={r['market_value']}")
    else:
        print(f"  NO POSITION in JQ records")

# 2. JQ trades for these stocks around 2026-05-26
jq_trades = pd.read_csv(T3 / "jq_trades_normalized.csv")
for s in TARGETS:
    t = jq_trades[(jq_trades["normalized_security_code"] == s) &
                  (jq_trades["trade_date"].isin(["2026-05-25", "2026-05-26", "2026-05-27"]))]
    if len(t) > 0:
        for _, r in t.iterrows():
            print(f"JQ trade {r['trade_date']}: {s} {r['side']} {r['quantity']}@{r['price']}")

# 3. Local trades after fix for these stocks
local_trades = pd.read_csv(OUT / "local_trades_after_fix.csv")
for s in TARGETS:
    t = local_trades[local_trades["code"] == s]
    if len(t) > 0:
        for _, r in t.iterrows():
            print(f"Local trade {str(r['time'])[:10]}: {s} {r['amount']}@{r['price']}")

# 4. HData prices for 2026-05-25 and 2026-05-26
import pyarrow.parquet as pq
hdata = pq.read_table(r"D:\Work Space\HData\data\processed\1d_stock\2026.parquet",
                      columns=["code","date","open","high","low","close","pre_close","pct_chg"])
hd = hdata.to_pandas()
hd["code"] = hd["code"].astype(str)
hd["date"] = hd["date"].astype(str)

def hdata_for(sec, dt_str):
    hc = sec.replace(".XSHE",".SZ").replace(".XSHG",".SH")
    hdt = dt_str.replace("-","")
    r = hd[(hd["code"] == hc) & (hd["date"] == hdt)]
    if len(r) > 0:
        return r.iloc[0].to_dict()
    return None

for s in TARGETS:
    for dt in ["2026-05-25", "2026-05-26"]:
        h = hdata_for(s, dt)
        if h:
            ll = round(h["pre_close"] * (0.80 if ".XSHE" in s else 0.90) / 0.01) * 0.01
            hl = round(h["pre_close"] * (1.20 if ".XSHE" in s else 1.10) / 0.01) * 0.01
            at_limit_up = h["close"] >= hl
            at_limit_dn = h["low"] <= ll
            print(f"HData {dt} {s}: O={h['open']:.2f} H={h['high']:.2f} L={h['low']:.2f} C={h['close']:.2f} PC={h['pre_close']:.2f} LL={ll:.2f} HL={hl:.2f} AtHL={at_limit_up} AtLL={at_limit_dn}")

# 5. Check yesterday_HL from TASK-003B engine logs
with open(T3 / "local_engine_logs.txt", "r", encoding="utf-8") as f:
    logs = f.readlines()

print("\n=== yesterday_HL from engine logs around 5/25-5/27 ===")
for line in logs:
    m = re.match(r'\[(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}\].*yesterday_HL=(.*)', line)
    if m:
        dt = m.group(1)
        if dt in ["2026-05-22", "2026-05-25", "2026-05-26", "2026-05-27"]:
            hl = m.group(2).strip()
            print(f"  {dt}: yesterday_HL=[{hl}]")
