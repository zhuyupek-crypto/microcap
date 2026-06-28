"""5/26 forensic: capture yesterday_HL, aggregate_target, order results for 4 stocks."""
import os, sys, json, hashlib
from pathlib import Path

LQ_ROOT = r"D:\Work Space\local_quant"
sys.path.insert(0, LQ_ROOT)
os.environ["HDATA_ROOT"] = "D:\\Work Space\\HData"
os.environ["LOCAL_QUANT_HDATA_SOURCE"] = "legacy"

STRATEGY_PATH = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
OUTPUT_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003e")
with open(STRATEGY_PATH, "rb") as f:
    assert hashlib.sha256(f.read()).hexdigest().upper() == "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"

import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
from engine.core import Engine

AUDIT_LOG = OUTPUT_DIR / "forensic_0526.jsonl"
if AUDIT_LOG.exists():
    AUDIT_LOG.unlink()

audit_seq = [0]
def audit_log(**kwargs):
    audit_seq[0] += 1
    e = {"event_sequence": audit_seq[0]}
    e.update(kwargs)
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

# Target stocks
TARGETS = ["300417.XSHE", "301167.XSHE", "600493.XSHG", "300535.XSHE"]

def make_hook(engine):
    ns = engine.namespace
    orig_trade = ns.get("trade")
    orig_prepare = ns.get("prepare_stock_list")
    orig_aggregate = ns.get("aggregate_target_values")
    orig_rebalance = ns.get("rebalance_to_aggregate_targets")
    orig_check = ns.get("check_limit_up")
    
    def wrap_prepare(ctx):
        r = orig_prepare(ctx) if orig_prepare else None
        g = ns.get("g")
        if g:
            hl = list(getattr(g, "yesterday_HL_list", []))
            audit_log(event="prepare_done", date=str(ctx.current_dt)[:10], yesterday_HL=hl,
                      has_any_target=any(s in hl for s in TARGETS))
        return r
    
    def wrap_aggregate(ctx):
        r = orig_aggregate(ctx) if orig_aggregate else None
        if r:
            for s in TARGETS:
                if s in r:
                    audit_log(event="aggregate_target", date=str(ctx.current_dt)[:10],
                              time=str(ctx.current_dt)[11:16], security=s, target_value=float(r[s]))
        return r
    
    def wrap_check(ctx):
        r = orig_check(ctx) if orig_check else None
        g = ns.get("g")
        if g:
            hl = list(getattr(g, "yesterday_HL_list", []))
            audit_log(event="check_limit_up_enter", date=str(ctx.current_dt)[:10],
                      time="14:00", yesterday_HL=hl,
                      has_any_target=any(s in hl for s in TARGETS))
            for s in TARGETS:
                if s in ctx.portfolio.positions:
                    pos = ctx.portfolio.positions[s]
                    audit_log(event="check_limit_up_position", date=str(ctx.current_dt)[:10],
                              time="14:00", security=s,
                              amount=pos.total_amount, value=float(pos.value), price=float(pos.price))
                    # Log if this position triggers an order
                    if s in hl:
                        audit_log(event="check_limit_up_would_act", date=str(ctx.current_dt)[:10],
                                  time="14:00", security=s, in_HL_list=True)
        return r
    
    def wrap_trade(ctx):
        g = ns.get("g")
        if g:
            audit_log(event="trade_enter", date=str(ctx.current_dt)[:10], time="09:30",
                      g_days=getattr(g, "days", None))
        r = orig_trade(ctx) if orig_trade else None
        return r
    
    # Install wraps
    for name, orig, wrapper in [
        ("prepare_stock_list", orig_prepare, wrap_prepare),
        ("trade", orig_trade, wrap_trade),
        ("aggregate_target_values", orig_aggregate, wrap_aggregate),
        ("check_limit_up", orig_check, wrap_check),
    ]:
        if orig:
            ns[name] = wrapper
            for i, (h, t) in enumerate(list(engine.handlers)):
                if h is orig:
                    engine.handlers[i] = (wrapper, t)

print("Running forensic backtest 2026-05-01 to 2026-05-27...")
try:
    with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
        code = f.read()
    engine = Engine(code, "2026-05-01", "2026-05-27", 1_000_000, "daily")
    engine.post_exec_hook = make_hook
    equity, trades, logs, metrics = engine.run()
    print(f"  {len(trades)} trades, {len(logs)} log lines")
except Exception as e:
    print(f"  ERROR in engine.run(): {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Save trades
if trades is not None and not trades.empty:
    trades.to_csv(OUTPUT_DIR / "forensic_0526_trades.csv", index=False)

# Read and summarize audit log
with open(AUDIT_LOG, "r", encoding="utf-8") as f:
    entries = [json.loads(l) for l in f if l.strip()]

# Query for 2026-05-26 events
may26 = [e for e in entries if "2026-05-26" in str(e.get("date", ""))]
print(f"\n=== 2026-05-26 forensic entries: {len(may26)} ===")
for e in may26:
    print(f"  [{e['event']}] date={e.get('date','')} time={e.get('time','')} {json.dumps({k:v for k,v in e.items() if k not in ('event_sequence','event','date')}, ensure_ascii=False)}")

# Also check 2026-05-24 (Friday) and 2026-05-25 (Monday) for yesterday_HL
for dt in ["2026-05-22", "2026-05-25"]:
    day_entries = [e for e in entries if dt in str(e.get("date", ""))]
    print(f"\n=== {dt} forensic entries: {len(day_entries)} ===")
    for e in day_entries:
        print(f"  [{e['event']}] time={e.get('time','')} {json.dumps({k:v for k,v in e.items() if k not in ('event_sequence','event','date')}, ensure_ascii=False)}")

print("\n\nDone. See forensic_0526.jsonl for full data.")
