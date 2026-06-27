#!/usr/bin/env python3
"""
TASK-MICROCAP-003B: Local backtest for JQ record range (2026-05-01 to 2026-06-24).
NON_AUTHORITATIVE_DIAGNOSTIC_RUN — initial_cash=1,000,000 (engine default, strong indirect evidence).
"""
import argparse, hashlib, json, os, sys, csv
from pathlib import Path
from datetime import datetime

LQ_ROOT = r"D:\Work Space\local_quant"
sys.path.insert(0, LQ_ROOT)
os.environ.setdefault("HDATA_ROOT", r"D:\Work Space\HData")
os.environ.setdefault("LOCAL_QUANT_HDATA_SOURCE", "legacy")

EXPECTED_SHA256 = "f363464fa55218c5b721d9286449c99a0c9acc097524b6f5f3db89a13af151d6"
STRATEGY_PATH = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
OUTPUT_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003")

import warnings, traceback
warnings.filterwarnings("ignore")


def verify_strategy(path):
    with open(path, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    if actual.lower() != EXPECTED_SHA256.lower():
        raise RuntimeError("SHA256 MISMATCH\n  Expected: %s\n  Actual:   %s" % (EXPECTED_SHA256.lower(), actual.lower()))
    return actual


def _git_cmd(cwd, *args):
    import subprocess
    try:
        return subprocess.check_output(["git"] + list(args), cwd=cwd, stderr=subprocess.STDOUT).decode().strip()
    except Exception:
        return "(unknown)"


def make_snapshot_capture(engine, snapshots):
    """Wrap strategy functions to capture pre/post trade states."""
    o_before = engine.namespace.get("before_trading_start")
    o_trade = engine.namespace.get("trade")

    def capture_state(label):
        ctx = engine.context
        port = ctx.portfolio if hasattr(ctx, "portfolio") else None
        if port is None:
            return
        ps = {}
        if hasattr(port, "positions"):
            for code, pos in port.positions.items():
                ps[code] = {
                    "quantity": getattr(pos, "total_amount", 0),
                    "price": getattr(pos, "price", 0),
                    "value": getattr(pos, "value", 0),
                }
        snapshots[ctx.current_dt.strftime("%Y%m%d") + "_" + label] = {
            "date": ctx.current_dt.strftime("%Y-%m-%d"),
            "label": label,
            "cash": float(port.available_cash) if hasattr(port, "available_cash") else None,
            "locked_cash": float(port.locked_cash) if hasattr(port, "locked_cash") else None,
            "positions_value": float(port.positions_value) if hasattr(port, "positions_value") else None,
            "total_value": float(port.total_value) if hasattr(port, "total_value") else None,
            "positions": ps,
        }

    if o_before:
        def w_before(ctx):
            capture_state("PRE_TRADE")
            return o_before(ctx)
        engine.namespace["before_trading_start"] = w_before
        for i, (h, t) in enumerate(list(engine.handlers)):
            if h is o_before:
                engine.handlers[i] = (w_before, t)

    if o_trade:
        def w_trade(ctx):
            capture_state("PRE_TRADE_INNER")
            result = o_trade(ctx)
            capture_state("POST_TRADE")
            return result
        engine.namespace["trade"] = w_trade
        for i, (h, t) in enumerate(list(engine.handlers)):
            if h is o_trade:
                engine.handlers[i] = (w_trade, t)

    # After engine.run(), capture END_OF_DAY from daily_portfolio_stats
    return snapshots


def run_backtest(start_date="2026-05-06", end_date="2026-06-24",
                 initial_cash=1_000_000, frequency="daily"):
    sha256 = verify_strategy(STRATEGY_PATH)
    from engine.core import Engine

    with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    snapshots = {}
    engine = Engine(strategy_code=strategy_code,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    frequency=frequency)
    engine.post_exec_hook = lambda e: make_snapshot_capture(e, snapshots)

    print("  Running backtest %s → %s  cash=%.0f ..." % (start_date, end_date, initial_cash))
    equity_df, trades_df, logs, metrics = engine.run()
    print("  Done: %d trading days, %d trades" % (len(equity_df), len(trades_df)))

    # Build EOD snapshots from daily_portfolio_stats
    eod_stats = getattr(engine, "daily_portfolio_stats", [])
    for eod in eod_stats:
        dt = eod["date"]
        key = dt.strftime("%Y%m%d") + "_END_OF_DAY"
        if key not in snapshots:
            ctx = engine.context
            port = ctx.portfolio if hasattr(ctx, "portfolio") else None
            ps = {}
            if port and hasattr(port, "positions"):
                for code, pos in port.positions.items():
                    ps[code] = {
                        "quantity": getattr(pos, "total_amount", 0),
                        "price": getattr(pos, "price", 0),
                        "value": getattr(pos, "value", 0),
                    }
            snapshots[key] = {
                "date": dt.strftime("%Y-%m-%d"),
                "label": "END_OF_DAY",
                "cash": float(eod.get("available_cash", 0)),
                "locked_cash": float(eod.get("frozen_cash", 0)),
                "positions_value": float(eod.get("positions_value", 0)),
                "total_value": float(eod.get("total_value", 0)),
                "positions": ps,
            }

    # Collect order details
    orders_list = []
    for oid, o in engine.orders.items():
        orders_list.append({
            "order_id": oid,
            "security": getattr(o, "security", ""),
            "side": getattr(o, "side", ""),
            "amount": getattr(o, "amount", 0),
            "filled": getattr(o, "filled", 0),
            "price": float(getattr(o, "price", 0) or 0),
            "status": str(getattr(o, "status", "")),
            "commission": float(getattr(o, "commission", 0) or 0),
        })

    # Build result
    result = {
        "run_type": "NON_AUTHORITATIVE_DIAGNOSTIC_RUN",
        "run_timestamp": datetime.now().isoformat(),
        "strategy_sha256": sha256,
        "initial_cash": initial_cash,
        "initial_cash_source": "FROM_ENGINE_DEFAULT (strong indirect evidence from all prior runs)",
        "start_date": start_date,
        "end_date": end_date,
        "frequency": frequency,
        "trading_days": len(equity_df),
        "fills": len(trades_df) if trades_df is not None and not trades_df.empty else 0,
        "orders_submitted": len([o for o in orders_list if o["status"] == "filled"]),
        "orders_rejected": len([o for o in orders_list if o["status"] == "rejected"]),
        "orders_open": len([o for o in orders_list if o["status"] == "open"]),
        "ending_cash": float(engine.context.portfolio.available_cash),
        "ending_total_value": float(engine.context.portfolio.total_value),
        "ending_positions": {
            k: {"amount": v.total_amount, "price": float(v.price), "value": float(v.value)}
            for k, v in engine.context.portfolio.positions.items()
        },
        "local_quant_branch": _git_cmd(LQ_ROOT, "rev-parse", "--abbrev-ref", "HEAD"),
        "local_quant_commit": _git_cmd(LQ_ROOT, "rev-parse", "HEAD"),
        "microcap_branch": _git_cmd(os.path.dirname(os.path.dirname(STRATEGY_PATH)), "rev-parse", "--abbrev-ref", "HEAD"),
        "microcap_commit": _git_cmd(os.path.dirname(os.path.dirname(STRATEGY_PATH)), "rev-parse", "HEAD"),
    }

    # Save outputs
    with open(OUTPUT_DIR / "local_run_manifest.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    # Save trades normalized
    if trades_df is not None and not trades_df.empty:
        tr = trades_df.to_dict(orient="records")
        with open(OUTPUT_DIR / "local_trades_normalized.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["trade_date", "code", "price", "amount", "commission", "side", "trade_id"])
            w.writeheader()
            for i, t in enumerate(tr):
                w.writerow({
                    "trade_date": str(t.get("time", ""))[:10],
                    "code": t.get("code", ""),
                    "price": float(t.get("price", 0)),
                    "amount": int(t.get("amount", 0)),
                    "commission": float(t.get("commission", 0)),
                    "side": t.get("side", "buy"),
                    "trade_id": t.get("trade_id", f"LOCAL_{i:04d}"),
                })

    # Save portfolio normalized
    with open(OUTPUT_DIR / "local_portfolio_normalized.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "cash", "total_value", "positions_value", "position_count"])
        w.writeheader()
        for eod in eod_stats:
            dt = eod["date"]
            pos_count = len(result["ending_positions"]) if dt == eod_stats[-1]["date"] else 0
            w.writerow({
                "date": dt.strftime("%Y-%m-%d"),
                "cash": float(eod.get("available_cash", 0)),
                "total_value": float(eod.get("total_value", 0)),
                "positions_value": float(eod.get("positions_value", 0)),
                "position_count": len(getattr(engine.context.portfolio, 'positions', {})) if hasattr(engine.context, 'portfolio') else 0,
            })

    # Save daily states (3-state snapshots)
    with open(OUTPUT_DIR / "local_daily_state.csv", "w", newline="", encoding="utf-8") as f:
        fields = ["date", "label", "cash", "locked_cash", "positions_value", "total_value", "position_count"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        keys_sorted = sorted(snapshots.keys())
        for k in keys_sorted:
            s = snapshots[k]
            w.writerow({
                "date": s["date"],
                "label": s["label"],
                "cash": s["cash"],
                "locked_cash": s["locked_cash"],
                "positions_value": s["positions_value"],
                "total_value": s["total_value"],
                "position_count": len(s["positions"]) if s.get("positions") else 0,
            })

    # Save logs
    with open(OUTPUT_DIR / "local_engine_logs.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(engine.logs))

    print("\n=== Local Run Complete ===")
    print("  Trading days: %d" % result["trading_days"])
    print("  Fills: %d" % result["fills"])
    print("  Orders (filled/rejected/open): %d / %d / %d" % (
        result["orders_submitted"], result["orders_rejected"], result["orders_open"]))
    print("  Ending cash: %.2f" % result["ending_cash"])
    print("  Ending total: %.2f" % result["ending_total_value"])
    print("  Ending positions: %d" % len(result["ending_positions"]))
    print("  Snapshots captured: %d" % len(snapshots))
    print("\n  Outputs:")
    for fn in ["local_run_manifest.json", "local_trades_normalized.csv",
               "local_portfolio_normalized.csv", "local_daily_state.csv", "local_engine_logs.txt"]:
        fp = OUTPUT_DIR / fn
        if fp.exists():
            print("    %s (%d bytes)" % (fn, fp.stat().st_size))
        else:
            print("    %s (MISSING!)" % fn)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2026-05-06")
    parser.add_argument("--end-date", default="2026-06-24")
    parser.add_argument("--initial-cash", type=float, default=1_000_000)
    parser.add_argument("--frequency", default="daily")
    args = parser.parse_args()

    print("=" * 60)
    print("TASK-MICROCAP-003B: Local re-run (DIAGNOSTIC)")
    print("=" * 60)
    print("\n[Verify] Strategy SHA...")
    sha = verify_strategy(STRATEGY_PATH)
    print("  SHA: %s ... %s" % (sha[:16], "OK" if sha.lower() == EXPECTED_SHA256.lower() else "MISMATCH!"))

    # Pre-check environment
    print("\n[Pre-check] Environment...")
    import pandas as pd
    cal = pd.read_parquet(
        os.path.join(os.environ["HDATA_ROOT"], "data", "processed", "metadata", "calendar.parquet")
    )
    trade_days = [d for d in cal["date"].tolist()
                  if args.start_date.replace("-", "") <= str(d) <= args.end_date.replace("-", "")]
    print("  Trade days in range: %d" % len(trade_days))

    # Run
    print("\n[Run] Starting backtest (this may take several minutes)...")
    try:
        result = run_backtest(
            start_date=args.start_date,
            end_date=args.end_date,
            initial_cash=args.initial_cash,
            frequency=args.frequency,
        )
        # Quick quality check
        print("\n[QC] Quick self-check...")
        jq_fills = 112  # from TASK-003A parse
        local_fills = result["fills"]
        diff = abs(local_fills - jq_fills)
        if diff <= 5:
            print("  Fill count OK: local=%d vs JQ=%d (diff=%d)" % (local_fills, jq_fills, diff))
        else:
            print("  Fill count WARNING: local=%d vs JQ=%d (diff=%d)" % (local_fills, jq_fills, diff))
        print("\n  *** NON_AUTHORITATIVE_DIAGNOSTIC_RUN ***")
        print("  initial_cash=1,000,000 (engine default)")
        print("  Results require validation against JQ records (TASK-003C)")
    except Exception as e:
        print("  RUN FAILED: %s" % e)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
