#!/usr/bin/env python3
"""Run original strategy with external audit wrapping (no strategy modification)."""
import os, sys, json, hashlib
from pathlib import Path

LQ_ROOT = r"D:\Work Space\local_quant"
sys.path.insert(0, LQ_ROOT)
os.environ.setdefault("HDATA_ROOT", r"D:\Work Space\HData")
os.environ.setdefault("LOCAL_QUANT_HDATA_SOURCE", "legacy")

STRATEGY_PATH = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
OUTPUT_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003d")
AUDIT_LOG = OUTPUT_DIR / "local_audit_20260514.jsonl"
EXPECTED_SHA = "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"

# Clear audit log
if AUDIT_LOG.exists():
    AUDIT_LOG.unlink()

# Verify SHA
with open(STRATEGY_PATH, "rb") as f:
    actual_sha = hashlib.sha256(f.read()).hexdigest().upper()
assert actual_sha == EXPECTED_SHA, f"SHA mismatch: {actual_sha}"

print("=" * 60)
print("TASK-003D1: External audit wrapper run")
print("=" * 60)
print(f"Strategy SHA: {actual_sha[:16]}...")

import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
from engine.core import Engine
import pandas as pd

# Audit state
audit_entries = []
audit_seq = [0]

def audit_log(event_type, **kwargs):
    audit_seq[0] += 1
    entry = {"event_sequence": audit_seq[0], "event_type": event_type}
    entry.update(kwargs)
    audit_entries.append(entry)
    # Also write to file immediately for crash safety
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

def make_audit_hook(engine):
    """Wrap strategy functions for audit logging."""
    ns = engine.namespace
    
    # Save originals
    orig_trade = ns.get("trade")
    orig_prepare = ns.get("prepare_stock_list")
    orig_aggregate = ns.get("aggregate_target_values")
    orig_rebalance = ns.get("rebalance_to_aggregate_targets")
    orig_report = ns.get("report_plan")
    orig_check_limit = ns.get("check_limit_up")
    orig_can_sell = ns.get("can_sell_today")
    orig_log_plan = ns.get("log_plan")
    orig_select = ns.get("select_smallest_market_cap")
    
    def wrap_prepare(ctx):
        result = orig_prepare(ctx) if orig_prepare else None
        g = ns.get("g")
        if g:
            audit_log("yesterday_HL_after_prepare",
                      current_dt=str(ctx.current_dt),
                      previous_date=str(ctx.previous_date),
                      yesterday_HL_list=list(getattr(g, "yesterday_HL_list", [])),
                      positions=list(ctx.portfolio.positions.keys()) if hasattr(ctx, "portfolio") else [])
        return result
    
    def wrap_trade(ctx):
        g = ns.get("g")
        if g:
            audit_log("trade_enter",
                      current_dt=str(ctx.current_dt),
                      previous_date=str(ctx.previous_date),
                      g_days=getattr(g, "days", None),
                      in_defensive=getattr(g, "in_defensive_mode", None),
                      portfolio_cash=float(ctx.portfolio.available_cash) if hasattr(ctx, "portfolio") else None,
                      portfolio_total=float(ctx.portfolio.total_value) if hasattr(ctx, "portfolio") else None)
        
        result = orig_trade(ctx) if orig_trade else None
        
        if g:
            audit_log("trade_exit",
                      current_dt=str(ctx.current_dt),
                      g_days=getattr(g, "days", None),
                      last_due_offsets=list(getattr(g, "last_due_offsets", [])),
                      portfolio_cash=float(ctx.portfolio.available_cash) if hasattr(ctx, "portfolio") else None)
        return result
    
    def wrap_aggregate(ctx):
        result = orig_aggregate(ctx) if orig_aggregate else None
        if result:
            audit_log("aggregate_target_result",
                      current_dt=str(ctx.current_dt),
                      targets={k: round(float(v), 2) for k, v in result.items()},
                      target_300405=float(result.get("300405.XSHE", 0.0)),
                      target_count=len(result))
            # Log phase state
            g = ns.get("g")
            if g:
                pt = getattr(g, "phase_targets", {})
                for offset, stocks in pt.items():
                    audit_log("phase_state",
                              current_dt=str(ctx.current_dt),
                              offset=offset,
                              stocks=list(stocks) if stocks else [])
        return result
    
    def wrap_rebalance(ctx):
        g = ns.get("g")
        # Log pre-rebalance state for 300405
        if g and hasattr(ctx, "portfolio"):
            pt = getattr(g, "phase_targets", {})
            if "300405.XSHE" in ctx.portfolio.positions:
                ph_membership = [off for off, stocks in pt.items() if "300405.XSHE" in stocks]
                pos = ctx.portfolio.positions["300405.XSHE"]
                audit_log("pre_rebalance_300405",
                          current_dt=str(ctx.current_dt),
                          phase_membership=ph_membership,
                          phase_count=len(ph_membership),
                          total_value=float(getattr(g, "days", 0)),
                          portfolio_total=float(ctx.portfolio.total_value),
                          position_amount=getattr(pos, "total_amount", 0),
                          position_value=getattr(pos, "value", 0),
                          yesterday_HL="300405.XSHE" in getattr(g, "yesterday_HL_list", []))
        
        result = orig_rebalance(ctx) if orig_rebalance else None
        return result
    
    def wrap_report(ctx):
        result = orig_report(ctx) if orig_report else None
        g = ns.get("g")
        if g:
            audit_log("report_plan_summary",
                      current_dt=str(ctx.current_dt),
                      g_days=getattr(g, "days", None),
                      defensive=getattr(g, "in_defensive_mode", None),
                      due_offsets=list(getattr(g, "last_due_offsets", [])),
                      yesterday_HL=list(getattr(g, "yesterday_HL_list", [])),
                      portfolio_cash=float(ctx.portfolio.available_cash) if hasattr(ctx, "portfolio") else None,
                      portfolio_total=float(ctx.portfolio.total_value) if hasattr(ctx, "portfolio") else None,
                      position_count=len(ctx.portfolio.positions) if hasattr(ctx, "portfolio") else 0)
        return result
    
    def wrap_select(ctx):
        result = orig_select(ctx) if orig_select else None
        g = ns.get("g")
        if g:
            audit_log("select_result",
                      current_dt=str(ctx.current_dt),
                      pool_size=len(result) if result else 0,
                      result=result if result else [])
        return result
    
    # Install wraps with exception safety
    def safe_wrap(name, wrapper):
        try:
            ns[name] = wrapper
            # Also update engine.handlers if this is a run_daily function
            for i, (h, t) in enumerate(list(engine.handlers)):
                if h is orig_trade and name == "trade":
                    engine.handlers[i] = (wrapper, t)
                elif h is orig_prepare and name == "prepare_stock_list":
                    engine.handlers[i] = (wrapper, t)
                elif h is orig_report and name == "report_plan":
                    engine.handlers[i] = (wrapper, t)
        except Exception as e:
            audit_log("wrap_error", function=name, error=str(e))
    
    # Wrap key functions
    if orig_prepare:
        ns["prepare_stock_list"] = wrap_prepare
        for i, (h, t) in enumerate(list(engine.handlers)):
            if h is orig_prepare:
                engine.handlers[i] = (wrap_prepare, t)
    if orig_trade:
        ns["trade"] = wrap_trade
        for i, (h, t) in enumerate(list(engine.handlers)):
            if h is orig_trade:
                engine.handlers[i] = (wrap_trade, t)
    if orig_aggregate:
        ns["aggregate_target_values"] = wrap_aggregate
    if orig_rebalance:
        ns["rebalance_to_aggregate_targets"] = wrap_rebalance
    if orig_report:
        ns["report_plan"] = wrap_report
        for i, (h, t) in enumerate(list(engine.handlers)):
            if h is orig_report:
                engine.handlers[i] = (wrap_report, t)
    if orig_select:
        ns["select_smallest_market_cap"] = wrap_select
    
    audit_log("audit_hook_installed",
              current_dt=str(engine.context.current_dt) if engine.context else None,
              wrapped_functions=["prepare_stock_list", "trade", "aggregate_target_values",
                                 "rebalance_to_aggregate_targets", "report_plan", "select_smallest_market_cap"])


print("\nCreating engine...")
with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
    code = f.read()

engine = Engine(strategy_code=code, start_date="2026-05-01", end_date="2026-05-15",
                initial_cash=1_000_000, frequency="daily")

engine.post_exec_hook = make_audit_hook

print("Running backtest...")
equity, trades, logs, metrics = engine.run()

print(f"\nBacktest complete:")
print(f"  Trading days: {len(equity)}")
print(f"  Trades: {len(trades)}")
print(f"  Final value: {metrics.get('total_return', 'N/A')}")

# Save
if trades is not None and not trades.empty:
    trades.to_csv(OUTPUT_DIR / "audit_v2_trades.csv", index=False)
    print(f"  Trades saved: {len(trades)}")

with open(OUTPUT_DIR / "audit_v2_engine_logs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(logs))
print(f"  Log lines: {len(logs)}")

with open(AUDIT_LOG, "r", encoding="utf-8") as f:
    audit_lines = [l for l in f if l.strip()]
print(f"  Audit log entries: {len(audit_lines)}")

# Check for errors
err_lines = [l for l in logs if "出错" in l or "Error" in l]
print(f"  Error lines: {len(err_lines)}")
for e in err_lines:
    print(f"    {e[:120]}")

# Reproduction check
jq_trades = pd.read_csv(OUTPUT_DIR.parent / "task_003" / "jq_trades_normalized.csv")
jq_trades["trade_date"] = jq_trades["trade_date"].astype(str)
for dt in ["2026-05-06", "2026-05-07", "2026-05-08", "2026-05-11", "2026-05-12", "2026-05-13", "2026-05-14"]:
    jq_cnt = len(jq_trades[jq_trades["trade_date"] == dt])
    local_cnt = len(trades[trades["time"].astype(str).str[:10] == dt]) if trades is not None and not trades.empty else 0
    flag = "" if jq_cnt == local_cnt else " *** MISMATCH ***"
    print(f"  {dt}: JQ={jq_cnt}, Local={local_cnt}{flag}")

# Show 300405-specific entries
print("\n=== 300405 audit entries on 2026-05-14 ===")
for line in audit_lines:
    e = json.loads(line)
    sec_context = json.dumps(e)
    if "300405" in sec_context and "2026-05-14" in sec_context:
        print(f"  [{e['event_type']}] {json.dumps({k: v for k, v in e.items() if k not in ('run_id', 'strategy_sha256', 'event_sequence')}, ensure_ascii=False)}")
