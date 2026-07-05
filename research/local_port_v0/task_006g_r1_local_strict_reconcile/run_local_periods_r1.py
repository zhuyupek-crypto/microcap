#!/usr/bin/env python3
"""
TASK-006G-R1 Stage 3: Local Same-Start Independent Backtests
=============================================================
Run local master strategy from same start as JQ records (1M cash, empty
portfolio) in RESEARCH mode. Cannot use r3_full slices (cumulative from 2020).

Outputs (under runs/):
- r1_2025_research/: equity.csv, trades.csv, closed_trades.csv,
                     manifest.json, performance_report.json, summary.md
- r1_2026m05_research/: same six files

Strategy: 微盘股-母版-20260627.py (immutable master)
Engine mode: research (causal, no JQ parity patches)
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"D:\Work Space\他山之石\微盘股")
TASK_DIR = PROJECT_ROOT / "research" / "local_port_v0" / "task_006g_r1_local_strict_reconcile"
TASK_005_DIR = PROJECT_ROOT / "research" / "local_port_v0" / "task_005_optimize"

# Add task_005 to path so we can import backtest_runner
sys.path.insert(0, str(TASK_005_DIR))

STRATEGY_PATH = PROJECT_ROOT / "微盘股-母版-20260627.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["2025", "2026", "both"], default="both")
    args = parser.parse_args()

    print("=" * 70)
    print("TASK-006G-R1 Stage 3: Local Same-Start Independent Backtests")
    print("=" * 70)
    print(f"Strategy: {STRATEGY_PATH}")
    print(f"Engine mode: research (causal, no JQ parity patches)")
    print(f"Initial cash: 1,000,000 (same as JQ records)")
    print()

    # Import the runner
    from backtest_runner import run_backtest

    runs = []
    if args.period in ("2025", "both"):
        runs.append({
            "tag": "r1_2025_research",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "output_dir": TASK_DIR / "runs" / "r1_2025_research",
            "label": "2025 full-year",
        })
    if args.period in ("2026", "both"):
        runs.append({
            "tag": "r1_2026m05_research",
            "start_date": "2026-05-01",
            "end_date": "2026-06-24",
            "output_dir": TASK_DIR / "runs" / "r1_2026m05_research",
            "label": "2026-05~06 fragment",
        })

    for r in runs:
        print(f"\n{'='*60}")
        print(f"Run: {r['tag']} ({r['label']})")
        print(f"  start={r['start_date']} end={r['end_date']} cash=1,000,000 mode=research")
        print(f"  output_dir={r['output_dir']}")
        print(f"{'='*60}")
        try:
            run_backtest(
                strategy_path=str(STRATEGY_PATH),
                tag=r["tag"],
                start_date=r["start_date"],
                end_date=r["end_date"],
                initial_cash=1_000_000,
                frequency="daily",
                output_dir=str(r["output_dir"]),
                engine_mode="research",
            )
            print(f"\n[OK] {r['tag']} completed.")
            # Verify outputs
            for fn in ("equity.csv", "trades.csv", "manifest.json",
                        "performance_report.json", "summary.md", "closed_trades.csv"):
                fp = r["output_dir"] / fn
                if fp.exists():
                    print(f"  {fn}: {fp.stat().st_size} bytes")
                else:
                    print(f"  {fn}: MISSING!")
        except Exception as e:
            import traceback
            print(f"\n[FAIL] {r['tag']}: {e}")
            traceback.print_exc()
            sys.exit(1)

    print("\n=== Stage 3 Complete ===")


if __name__ == "__main__":
    main()
