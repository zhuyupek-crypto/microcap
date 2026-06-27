"""Check HData price data for key securities."""
import pyarrow.parquet as pq
import pandas as pd

t = pq.read_table(r'D:\Work Space\HData\data\processed\1d_stock\2026.parquet',
                  columns=['code','date','open','high','low','close','pre_close','pct_chg'])
df = t.to_pandas()
df['code'] = df['code'].astype(str)
df['date'] = df['date'].astype(str).str[:10]

for sec in ['300405.XSHE', '301098.XSHE']:
    p = df[df['code'] == sec]
    print(f'=== {sec} HData 2026-05 ===')
    for _, r in p[p['date'].str.startswith('2026-05')].iterrows():
        print(f'  {r["date"]}: O={r["open"]} H={r["high"]} L={r["low"]} C={r["close"]} PC={r["pre_close"]} Pct={r["pct_chg"]}')
    print()

# Check 300405 on 5-14 specifically
p = df[df['code'] == '300405.XSHE']
r14 = p[p['date'] == '2026-05-14']
if len(r14) > 0:
    r = r14.iloc[0]
    pc = r['pre_close']
    ll = round(pc * 0.80 / 0.01) * 0.01
    print(f'300405 2026-05-14: prev_close={pc}, low_limit(20%)={ll}')
    print(f'  low={r["low"]}, close={r["close"]}')
    print(f'  Is limit down? low <= low_limit: {r["low"] <= ll}')
