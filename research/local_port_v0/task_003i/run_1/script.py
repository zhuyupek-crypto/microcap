
import os, sys, hashlib
sys.path.insert(0, r"D:\Work Space\HData\scripts")
sys.path.insert(0, r"D:\Work Space\HData")
sys.path.insert(0, r"D:\Work Space\local_quant")
os.environ["HDATA_ROOT"] = "D:\\Work Space\\HData"
os.environ["LOCAL_QUANT_HDATA_SOURCE"] = "legacy"
os.environ["PYTHONHASHSEED"] = "0"
import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

# Clear ALL hdata_reader caches (both import paths)
from core import hdata_reader as hdr_c
import scripts.core.hdata_reader as hdr_s
hdr_c._LOADED_YEARS.clear()
hdr_c._PIVOT_CACHE.clear()
hdr_s._LOADED_YEARS.clear()
hdr_s._PIVOT_CACHE.clear()

from engine.core import Engine
import random, numpy as np
random.seed(42)
np.random.seed(42)

sp = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
with open(sp, "rb") as f:
    assert hashlib.sha256(f.read()).hexdigest().upper() == "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"
code = open(sp, "r", encoding="utf-8").read()

e = Engine(code, "2026-05-01", "2026-06-24", 1_000_000)
if hasattr(e.data_api, "_history_cache"):
    e.data_api._history_cache.clear()
if hasattr(e.data_api, "_price_records"):
    e.data_api._price_records.clear()

eq, tr, logs, met = e.run()
OUT = r"D:\\Work Space\\他山之石\\微盘股\\research\\local_port_v0\\task_003i\\run_1"
tr.to_csv(os.path.join(OUT, "trades.csv"), index=False)
with open(os.path.join(OUT, "count.txt"), "w") as f:
    f.write(str(len(tr)))
print(f"Trades: {len(tr)}")
