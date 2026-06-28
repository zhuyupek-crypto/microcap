"""Minimal engine test to verify it works in task_003e directory."""
import os, sys
sys.path.insert(0, r"D:\Work Space\local_quant")
os.environ["HDATA_ROOT"] = "D:\\Work Space\\HData"
os.environ["LOCAL_QUANT_HDATA_SOURCE"] = "legacy"
import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
from engine.core import Engine

code = """
from jqdata import *
def initialize(c):
    run_daily(trade, "09:30")
def trade(c):
    g.done = True
"""

print("Creating engine...")
e = Engine(code, "2026-05-01", "2026-05-15", 1000000)
print("Running...")
eq, tr, logs, met = e.run()
print(f"Trades: {len(tr)}, Logs: {len(logs)}")
