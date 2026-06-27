"""Analyze the audit log for key events."""
import json

with open("local_audit_20260514.jsonl", "r", encoding="utf-8") as f:
    entries = [json.loads(line) for line in f if line.strip()]

print("Total entries:", len(entries))

# Trade enters
print("\n=== TRADE_ENTER ===")
for e in entries:
    if e["event_type"] == "trade_enter":
        print(f"  {e.get('current_dt','?')}: g_days={e.get('g_days_before')}")

# Due offsets
print("\n=== DUE_OFFSETS ===")
for e in entries:
    if e["event_type"] == "trade_due_offsets":
        print(f"  {e.get('current_dt','?')}: offsets={e.get('due_offsets')}")

# Rebalance plan
print("\n=== REBALANCE_PLAN ===")
for e in entries:
    if e["event_type"] == "rebalance_plan":
        sp = len(e.get("sell_plan", []))
        bp = len(e.get("buy_plan", []))
        print(f"  {e.get('current_dt','?')}: sell_plan={sp}, buy_plan={bp}")
        # Print 300405 specific
        for item in e.get("sell_plan", []):
            if "300405" in str(item.get("stock","")):
                print(f"    SELL 300405: {item}")
        for item in e.get("buy_plan", []):
            if "300405" in str(item.get("stock","")):
                print(f"    BUY 300405: {item}")

# Orders
print("\n=== ORDER_TARGET_VALUE ===")
ord_count = sum(1 for e in entries if e["event_type"] == "order_target_value")
print(f"Total orders: {ord_count}")
for e in entries:
    if e["event_type"] == "order_target_value":
        d = {
            "dt": e.get("current_dt","?"),
            "sec": e.get("security","?"),
            "target": e.get("target_value"),
            "filled": e.get("filled_amount"),
            "status": e.get("order_status"),
            "type": e.get("order_type","?"),
        }
        print(f"  {d}")

# Sell decisions for 300405
print("\n=== SELL_DECISIONS for 300405 ===")
for e in entries:
    if e["event_type"] == "sell_decision" and "300405" in str(e.get("security","")):
        print(f"  {e.get('current_dt','?')}: {json.dumps(e, ensure_ascii=False)}")

# Phase targets for 300405
print("\n=== PHASE TARGETS ===")
for e in entries:
    if e["event_type"] == "trade_phase_target_selected":
        print(f"  {e.get('current_dt','?')}: offset={e.get('phase_offset')}, targets={e.get('target_list')}")

# Aggregate targets
print("\n=== AGGREGATE TARGET ===")
for e in entries:
    if e["event_type"] == "aggregate_target_result":
        print(f"  {e.get('current_dt','?')}: target_300405={e.get('target_300405')}, total={e.get('target_count')}")

# Stock pool
print("\n=== STOCK POOL ===")
for e in entries:
    if e["event_type"] == "stock_pool_result":
        print(f"  {e.get('current_dt','?')}: pool={e.get('pool_size')} (before_vol={e.get('pool_size_before_volume')})")

# Initialize
for e in entries:
    if e["event_type"] == "initialize":
        print(f"\n=== INIT ===")
        for k, v in e.items():
            if k not in ("run_id","strategy_sha256","event_sequence","event_type"):
                print(f"  {k}: {v}")
