"""Full audit: trace every get_price call layer for normal vs abnormal cases."""
import os, sys, json, hashlib, time
from pathlib import Path

ROOT = r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003f"
OUT = Path(ROOT)
LQ_ROOT = r"D:\Work Space\local_quant"
sys.path.insert(0, LQ_ROOT)
os.environ["HDATA_ROOT"] = "D:\\Work Space\\HData"
os.environ["LOCAL_QUANT_HDATA_SOURCE"] = "legacy"

import pandas as pd
import numpy as np

# Verify SHA
EXP = "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"
sp = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
with open(sp, "rb") as f:
    assert hashlib.sha256(f.read()).hexdigest().upper() == EXP

import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

# ============================================================
# Capture environment
# ============================================================
env = {
    "LOCAL_QUANT_HDATA_SOURCE": os.environ.get("LOCAL_QUANT_HDATA_SOURCE"),
    "HDATA_ROOT": os.environ.get("HDATA_ROOT"),
    "LOCALQUANT_DATA_ROOT": os.environ.get("LOCALQUANT_DATA_ROOT"),
    "cwd": os.getcwd(),
    "lq_commit": "eb07910219d54824c3a92c0226b4dba10f2c5291",
    "mc_commit": "f19574a5faa64ff069b85e4a390d29e3ae08f758",
    "strategy_sha": EXP,
}

# Check _USING_CORE
import engine.data_api as eda
env["_USING_CORE"] = str(getattr(eda, "_USING_CORE", "NOT_FOUND"))
# Check data_root
env["DataAPI_default_data_root"] = str(getattr(eda.DataAPI.__init__, "__defaults__", (None,)))

with open(OUT / "audit_environment.json", "w", encoding="utf-8") as f:
    json.dump(env, f, indent=2)

print(f"Environment: _USING_CORE={env['_USING_CORE']}, HDATA_SOURCE={env['LOCAL_QUANT_HDATA_SOURCE']}")

# ============================================================
# Audit log
# ============================================================
trace_id_counter = [0]
audit_entries = []
TRACE_LOG = OUT / "get_price_trace.jsonl"

def audit(etype, **kw):
    trace_id_counter[0] += 1
    e = {"trace": trace_id_counter[0], "type": etype}
    e.update(kw)
    e["ts"] = time.time()
    audit_entries.append(e)
    with open(TRACE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, default=str, ensure_ascii=False) + "\n")

def wrap_method(obj, method_name, wrapper_name):
    orig = getattr(obj, method_name, None)
    if orig is None:
        audit("wrap_skip", method=method_name, reason="not_found")
        return None
    def traced(*args, **kwargs):
        parent_trace = trace_id_counter[0]
        audit(f"call_{wrapper_name}", method=method_name, args=str(args)[:200], kwargs=str(kwargs)[:200])
        try:
            # orig is bound method; skip args[0] (self) if present
            call_args = args[1:] if args and hasattr(orig, '__self__') else args
            result = orig(*call_args, **kwargs)
            info = {}
            if hasattr(result, 'shape'):
                info = {"shape": list(result.shape), "columns": list(result.columns) if hasattr(result, 'columns') else []}
            audit(f"return_{wrapper_name}", method=method_name, **info)
            return result
        except Exception as e:
            audit(f"error_{wrapper_name}", method=method_name, error=str(e))
            raise
    setattr(obj, method_name, traced)
    return traced

# ============================================================
# Create engine and wrap DataAPI methods
# ============================================================
print("Creating engine...")
from engine.core import Engine

code = open(sp, "r", encoding="utf-8").read()
engine = Engine(code, "2026-05-01", "2026-05-27", 1_000_000, "daily")
da = engine.data_api

# Wrap only DataAPI.get_price - minimal, proven approach
orig_get_price = da.get_price
def traced_get_price(security, start_date=None, end_date=None, frequency='daily', fields=None, fq=None, count=None, panel=None):
    audit("get_price_call", sec=security, sd=str(start_date)[:10], ed=str(end_date)[:10],
          freq=frequency, fields=str(fields), count=count, fq=str(fq))
    result = orig_get_price(security=security, start_date=start_date, end_date=end_date,
                            frequency=frequency, fields=fields, fq=fq, count=count, panel=panel)
    ret_info = {}
    if result is not None and hasattr(result, 'shape'):
        ret_info = {"shape": list(result.shape), "cols": list(result.columns) if hasattr(result, 'columns') else []}
        if not result.empty:
            for col in ["close", "high_limit", "pre_close"]:
                if col in result.columns:
                    ret_info[col] = float(result[col].iloc[0])
    audit("get_price_return", **ret_info)
    return result
da.get_price = traced_get_price

# Also wrap namespace get_price for strategy-level trace
ns = engine.namespace
orig_ns_gp = ns.get("get_price")
if orig_ns_gp:
    def traced_ns_gp(*args, **kwargs):
        audit("strategy_get_price_call", args=str(args)[:200], kwargs=str(kwargs)[:200])
        result = orig_ns_gp(*args, **kwargs)
        ret_info = {}
        if result is not None and hasattr(result, 'shape'):
            ret_info = {"shape": list(result.shape), "columns": list(result.columns) if hasattr(result, 'columns') else []}
            if not result.empty and "close" in result.columns and "high_limit" in result.columns:
                ret_info["close"] = float(result["close"].iloc[0])
                ret_info["high_limit"] = float(result["high_limit"].iloc[0])
                ret_info["close_ge_hl"] = float(result["close"].iloc[0]) >= float(result["high_limit"].iloc[0])
        audit("strategy_get_price_return", **ret_info)
        return result
    ns["get_price"] = traced_ns_gp
    # Also update handlers
    for i, (h, t) in enumerate(list(engine.handlers)):
        if h is orig_ns_gp:
            engine.handlers[i] = (traced_ns_gp, t)
    audit("strategy_get_price_wrapped")

# Wrap prepare_stock_list and check_limit_up in namespace
def wrap_strategy_func(name):
    orig = ns.get(name)
    if orig:
        def wrapper(ctx):
            audit(f"strategy_{name}_enter", date=str(ctx.current_dt)[:10], time=str(ctx.current_dt)[11:16])
            try:
                r = orig(ctx)
                audit(f"strategy_{name}_exit", date=str(ctx.current_dt)[:10])
                return r
            except Exception as e:
                audit(f"strategy_{name}_error", error=str(e))
                raise
        ns[name] = wrapper
        for i, (h, t) in enumerate(list(engine.handlers)):
            if h is orig:
                engine.handlers[i] = (wrapper, t)
        audit(f"strategy_{name}_wrapped")

wrap_strategy_func("prepare_stock_list")
wrap_strategy_func("check_limit_up")
# Do NOT wrap trade - too complex, may cause issues

# ============================================================
# Run backtest
# ============================================================
print("Running backtest...")
eq, trades, logs, metrics = engine.run()

print(f"  Trades: {len(trades)}")
print(f"  Logs: {len(logs)}")

trades.to_csv(OUT / "audit_trades.csv", index=False)

# ============================================================
# Extract traces for normal and abnormal cases
# ============================================================
# First, filter entries by stock code
norm_entries = [e for e in audit_entries if "300665" in str(e)]
abn_entries = [e for e in audit_entries if any(s in str(e) for s in ["300417", "301167", "600493", "300535"])]

print(f"\nNormal case (300665) entries: {len(norm_entries)}")
print(f"Abnormal case entries: {len(abn_entries)}")

# Extract strategy get_price returns for normal vs abnormal
for label, entries in [("NORMAL_300665", norm_entries), ("ABNORMAL_4STOCKS", abn_entries)]:
    print(f"\n=== {label} ===")
    for e in entries:
        etype = e.get("type", "")
        if "strategy_get_price_return" in etype:
            dt = e.get("date", "?")
            if "2026-05-18" in str(e) or "2026-05-19" in str(e) or "2026-05-25" in str(e):
                print(f"  {e.get('date','?')} close={e.get('close')} hl={e.get('high_limit')} ge={e.get('close_ge_hl')}")

# Explicitly check 300665 on 2026-05-18 high_limit
print("\n=== 300665 high_limit check ===")
for e in audit_entries:
    if "300665" in str(e) and ("close" in str(e) or "high_limit" in str(e)):
        if "2026-05-18" in str(e) or "2026-05-19" in str(e):
            print(f"  [{e.get('type')}] {json.dumps({k:v for k,v in e.items() if k not in ('ts',)}, default=str)[:300]}")

print("\nDone. See get_price_trace.jsonl for full trace.")
