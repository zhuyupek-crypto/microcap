#!/usr/bin/env python3
"""
TASK-005 优化工作通用回测运行器
=================================

- 输入：策略 .py 路径 + 标签
- 输出：扩展指标 JSON + trades CSV + equity CSV + engine logs
- 指标含：年化收益、夏普、最大回撤、波动率、换手率、胜率、单股最大亏损、防御月份占比等

可被 compare_with_baseline.py 调用，也可独立运行。
"""
import argparse, hashlib, json, os, sys, csv, warnings, traceback
from pathlib import Path
from datetime import datetime
import shutil

warnings.filterwarnings("ignore")

LQ_ROOT = r"D:\Work Space\local_quant"
sys.path.insert(0, LQ_ROOT)
os.environ.setdefault("HDATA_ROOT", r"D:\Work Space\HData")
os.environ.setdefault("LOCAL_QUANT_HDATA_SOURCE", "legacy")

# 默认输出目录：本脚本所在目录下的 runs/<tag>/
SCRIPT_DIR = Path(__file__).resolve().parent
BASELINE_STRATEGY = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"


def _git_cmd(cwd, *args):
    import subprocess
    try:
        return subprocess.check_output(
            ["git"] + list(args), cwd=cwd, stderr=subprocess.STDOUT
        ).decode().strip()
    except Exception:
        return "(unknown)"


def extended_metrics(equity_df, trades_df, initial_cash):
    """在 engine.performance.calculate_metrics 基础上扩展指标。"""
    import numpy as np
    if equity_df.empty:
        return {}

    eq = equity_df.copy()
    eq["return"] = eq["value"].pct_change().fillna(0)

    total_return = (eq["value"].iloc[-1] / eq["value"].iloc[0]) - 1
    active_days = len(eq)
    annual_return = (1 + total_return) ** (252 / active_days) - 1 if active_days > 0 else 0
    returns = eq["return"].values
    volatility = float(np.std(returns, ddof=1) * np.sqrt(252)) if len(returns) > 1 else 0
    sharpe = (annual_return - 0.03) / volatility if volatility > 0 else 0

    peak = np.maximum.accumulate(eq["value"].values)
    drawdown = (eq["value"].values - peak) / peak
    max_drawdown = float(np.min(drawdown))
    # 最大回撤持续天数（peak 到 trough 的天数）
    max_dd_end = int(np.argmin(drawdown))
    max_dd_start = int(np.argmax(peak[:max_dd_end + 1])) if max_dd_end > 0 else 0
    max_dd_duration = max_dd_end - max_dd_start

    # Calmar
    calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

    # 换手率（双边成交额 / 期初权益，年化）
    if trades_df is not None and not trades_df.empty:
        turnover_value = float((trades_df["price"] * trades_df["amount"].abs()).sum())
        annual_turnover = turnover_value / initial_cash * (252 / active_days) if active_days > 0 else 0
        # 胜率：按 code 分组，比较同 code 的买卖方向
        # trades_df 含 side / amount（带方向）
        buy_vol = trades_df[trades_df["amount"] > 0].groupby("code")["amount"].sum()
        sell_vol = trades_df[trades_df["amount"] < 0].groupby("code")["amount"].sum().abs()
        # 单笔胜率：每笔卖出价 > 平均买入价视为胜
        # 简化：按 code 计算加权平均买入价 vs 加权平均卖出价
        win_count, total_close_count = 0, 0
        for code in sell_vol.index:
            if code not in buy_vol.index:
                continue
            buy_rows = trades_df[(trades_df["code"] == code) & (trades_df["amount"] > 0)]
            sell_rows = trades_df[(trades_df["code"] == code) & (trades_df["amount"] < 0)]
            if buy_rows.empty or sell_rows.empty:
                continue
            avg_buy = (buy_rows["price"] * buy_rows["amount"]).sum() / buy_rows["amount"].sum()
            for _, s in sell_rows.iterrows():
                total_close_count += 1
                if s["price"] > avg_buy:
                    win_count += 1
        win_rate = win_count / total_close_count if total_close_count > 0 else 0
        n_fills = len(trades_df)
    else:
        annual_turnover = 0
        win_rate = 0
        n_fills = 0

    return {
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_drawdown),
        "max_dd_duration_days": int(max_dd_duration),
        "volatility": float(volatility),
        "calmar": float(calmar),
        "annual_turnover": float(annual_turnover),
        "win_rate": float(win_rate),
        "n_fills": int(n_fills),
        "ending_value": float(eq["value"].iloc[-1]),
        "trading_days": int(active_days),
    }


def run_backtest(strategy_path, tag, start_date="2025-01-02", end_date="2025-12-31",
                 initial_cash=1_000_000, frequency="daily", output_dir=None):
    """运行单次回测并保存结果到 output_dir/runs/<tag>/。"""
    from engine.core import Engine

    if output_dir is None:
        output_dir = SCRIPT_DIR / "runs" / tag
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(strategy_path, "r", encoding="utf-8") as f:
        strategy_code = f.read()
    sha256 = hashlib.sha256(strategy_code.encode()).hexdigest()

    # 复制策略文件以便复现
    shutil.copy(strategy_path, output_dir / "strategy.py")

    print(f"[{tag}] Running backtest {start_date} -> {end_date} cash={initial_cash:.0f}")
    engine = Engine(
        strategy_code=strategy_code,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        frequency=frequency,
    )
    equity_df, trades_df, logs, metrics = engine.run()
    ext = extended_metrics(equity_df, trades_df, initial_cash)

    print(f"[{tag}] Done: {ext.get('trading_days', 0)} days, "
          f"{ext.get('n_fills', 0)} fills, "
          f"ending={ext.get('ending_value', 0):.2f}, "
          f"annual_ret={ext.get('annual_return', 0):.2%}, "
          f"sharpe={ext.get('sharpe', 0):.2f}, "
          f"maxDD={ext.get('max_drawdown', 0):.2%}")

    # 保存
    equity_df.to_csv(output_dir / "equity.csv", index=False)
    if trades_df is not None and not trades_df.empty:
        trades_df.to_csv(output_dir / "trades.csv", index=False)
    with open(output_dir / "engine_logs.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(engine.logs))

    result = {
        "tag": tag,
        "strategy_sha256": sha256[:16],
        "strategy_path": str(strategy_path),
        "run_timestamp": datetime.now().isoformat(),
        "initial_cash": initial_cash,
        "start_date": start_date,
        "end_date": end_date,
        "frequency": frequency,
        "local_quant_branch": _git_cmd(LQ_ROOT, "rev-parse", "--abbrev-ref", "HEAD"),
        "local_quant_commit": _git_cmd(LQ_ROOT, "rev-parse", "HEAD")[:10],
        "metrics": ext,
        "orders_filled": len([o for o in engine.orders.values() if str(getattr(o, 'status', '')) == 'filled']),
        "orders_rejected": len([o for o in engine.orders.values() if str(getattr(o, 'status', '')) == 'rejected']),
        "ending_positions": {
            k: {"amount": v.total_amount, "price": float(v.price), "value": float(v.value)}
            for k, v in engine.context.portfolio.positions.items()
        },
    }
    with open(output_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return result


def main():
    p = argparse.ArgumentParser(description="TASK-005 通用回测运行器")
    p.add_argument("--strategy", default=BASELINE_STRATEGY)
    p.add_argument("--tag", default="baseline")
    p.add_argument("--start-date", default="2025-01-02")
    p.add_argument("--end-date", default="2025-12-31")
    p.add_argument("--initial-cash", type=float, default=1_000_000)
    args = p.parse_args()

    print("=" * 60)
    print("TASK-005 Backtest Runner")
    print("=" * 60)
    print(f"  Engine : {LQ_ROOT}")
    print(f"  Data   : {os.environ['HDATA_ROOT']}")
    print(f"  Branch : {_git_cmd(LQ_ROOT, 'rev-parse', '--abbrev-ref', 'HEAD')}")
    print(f"  Commit : {_git_cmd(LQ_ROOT, 'rev-parse', 'HEAD')[:10]}")
    print(f"  Strategy: {args.strategy}")
    print()

    try:
        run_backtest(args.strategy, args.tag,
                     start_date=args.start_date, end_date=args.end_date,
                     initial_cash=args.initial_cash)
    except Exception as e:
        print(f"  RUN FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
