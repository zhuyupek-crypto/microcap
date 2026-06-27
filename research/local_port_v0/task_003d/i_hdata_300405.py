"""Check HData for 300405 on 2026-05-13 to test yesterday_HL hypothesis."""
import pyarrow.parquet as pq
import pandas as pd

def norm(sec):
    return sec.replace(".XSHE", ".SZ").replace(".XSHG", ".SH")

def check_300405():
    fp = r"D:\Work Space\HData\data\processed\1d_stock\2026.parquet"
    t = pq.read_table(fp, columns=["code","date","open","high","low","close","pre_close","pct_chg","vol","amount"])
    df = t.to_pandas()
    df["code"] = df["code"].astype(str)
    df["date"] = df["date"].astype(str)
    
    hcode = norm("300405.XSHE")
    p = df[df["code"] == hcode].copy()
    p = p[p["date"].between("20260501", "20260520")]
    
    if len(p) == 0:
        print("NO DATA FOUND for 300405 in 2026-05")
        # Debug: check what codes are available
        print("Sample SZ codes:", df[df["code"].str.endswith(".SZ") & df["date"].between("20260501", "20260510")]["code"].unique()[:5])
        return
    
    print("=== 300405.XSHE in HData 2026-05 ===")
    for _, r in p.iterrows():
        prev = r["pre_close"]
        ll = round(prev * 0.80 / 0.01) * 0.01
        hl = round(prev * 1.20 / 0.01) * 0.01
        at_high_limit = r["close"] >= hl
        print(f"  {r['date']}: O={r['open']} H={r['high']} L={r['low']} C={r['close']} PC={prev} LL={ll} HL={hl} AtHL={at_high_limit}")

    # Specifically check 2026-05-13
    r13 = p[p["date"] == "20260513"]
    if len(r13) > 0:
        r = r13.iloc[0]
        prev = r["pre_close"]
        hl = round(prev * 1.20 / 0.01) * 0.01
        print(f"\n2026-05-13: close={r['close']} >= high_limit={hl}? {r['close'] >= hl}")
        print(f"  pct_chg={r['pct_chg']}")

check_300405()
