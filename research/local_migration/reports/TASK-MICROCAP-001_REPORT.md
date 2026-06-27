# TASK-MICROCAP-001 任务报告（修正版 TASK-MICROCAP-001B 生效）

> 本报告已根据 TASK-MICROCAP-001B 要求更新。统计以 `compatibility_result.json` 为唯一数据源。

## 1. 执行摘要

本任务完成了微盘股策略（`微盘股-母版-20260627.py`）的基线冻结，并系统性地评估了将其迁移到 `local_quant` 框架所需的依赖覆盖情况。

**最终结论：local_quant 存在 5 个 P0 缺口（阻止正确运行）、2 个 P1 缺口（可能导致结果偏差）和 3 个 P2 缺口（影响实盘真实性）**，无法在当前状态下直接运行策略。GAP-005（09:30语义）和 GAP-008（ETF费用）经实证验证已关闭。

---

## 2. 仓库状态

| 项目 | 值 |
|---|---|
| **microcap 基线提交** | `8290ca3b0368aa6496ac801ee02ae4456fea8987` |
| **microcap 分支** | `research/local-port-v0` |
| **microcap 远端** | `https://github.com/zhuyupek-crypto/microcap` |
| **策略 SHA-256** | `f363464fa55218c5b721d9286449c99a0c9acc097524b6f5f3db89a13af151d6` |
| **local_quant 审计分支** | `task/qixing-engine-performance` |
| **local_quant 审计 HEAD** | `2a3167efd1dbbe6a2cf7a51391fa33762fe2f1df` |
| **local_quant 远端** | `https://github.com/zhuyupek-crypto/local_quant` |
| **Python 版本** | 3.14.3 |
| **平台** | win32 |

---

## 3. 母版完整性

- **SHA-256 确认一致**：`f363464fa55218c5b721d9286449c99a0c9acc097524b6f5f3db89a13af151d6`，未发生任何字节变化
- **git diff 检查**：HEAD 对母版无修改
- **关键参数检查**：所有冻结参数均未改变
- **local_quant 未修改**：本任务未修改 local_quant 任何代码

---

## 4. API 覆盖统计

### 修正前（TASK-MICROCAP-001 原始统计）

| 状态 | 数量 |
|---|---|
| **PASS** | 31 |
| **PARTIAL** | 3 |
| **MISSING** | 4 |
| **UNKNOWN** | 0 |

### 修正后（TASK-MICROCAP-001B 最终统计）

| 状态 | 数量 |
|---|---|
| **PASS** | 30 |
| **PARTIAL** | 3 |
| **MISSING** | 5 |
| **UNKNOWN** | 0 |
| **合计** | 38 |

### 修正差异

- PASS 减 1（`log.warn` 从误判 PASS 修正为 MISSING）
- MISSING 加 1（新增 `log.warn`）
- GAP-005（09:30语义）已关闭：实证验证通过
- GAP-008（ETF费用）已关闭：实证验证通过

---

## 5. P0/P1/P2 缺口数量

| 优先级 | 修正前 | 修正后 | 变化 |
|---|---|---|---|
| **P0（阻止正确运行）** | 4 | **5** | +1（GAP-012: log.warn 缺失） |
| **P1（结果可能明显偏离）** | 4 | **2** | -2（GAP-005/008已关闭） |
| **P2（影响实盘真实性）** | 3 | **3** | 不变 |
| **合计** | 11 | **10** | -1（GAP-005/008关闭，GAP-012新增） |

---

## 6. 已确认的重要缺口

### 关闭的误报缺口

- **GAP-005（09:30价格语义差异）**：已关闭。实证测试 `test_current_data_0930_last_price_uses_open` 通过真实Engine实例化验证：2024-01-03 09:30, 000001.XSHE, last_price=9.19=当日开盘价(9.19)≠前收盘(9.21)。
- **GAP-008（防御ETF手续费类型）**：已关闭。实证测试 `test_511880_uses_etf_cost_model` 通过真实Engine验证：`_order_costs` 有独立ETF条目(close_tax=0)，不受 type='stock' 设置影响。

### P0（必须修复才能运行）

| 编号 | 接口 | 影响 |
|---|---|---|
| GAP-001 | `position.value` 缺失 | 运行时直接 AttributeError，调仓逻辑中断 |
| GAP-002 | `cash_flow.net_operate_cash_flow` 表缺失 | 财务风险过滤静默失效 |
| GAP-003 | `balance.total_liability` 表缺失 | 资产负债率计算不能进行 |
| GAP-004 | `balance.total_assets` 表缺失 | 同 GAP-003 |
| **GAP-012** | **`log.warn` 缺失** | **恶化交互**：cash_flow/balance 查询失败→except→`log.warn`→`AttributeError`→策略中断 |

### P1（可能导致结果大幅偏差）

| 编号 | 接口 | 影响 |
|---|---|---|
| GAP-006 | 财务数据公告日语义不完整 | ROE 可能包含未来数据 |
| GAP-007 | `set_option("avoid_future_data")` 被忽略 | 潜在未来数据问题不被检测 |

### P2（影响实盘真实性）

| 编号 | 接口 | 影响 |
|---|---|---|
| GAP-009 | 部分成交处理 | 间接影响 |
| GAP-010 | 市场冲击成本 | 微盘股流动性差 |
| GAP-011 | 连续跌停退出 | 策略不处理连续跌停 |

---

## 7. 尚无法确认的项目

- `get_price` 的前瞻数据补丁在单股票+指定 fields 情况下的完整覆盖
- `stock_indicator` 数据中 `roe` 字段是否在历史截面中已包含未来信息

---

## 8. 运行过的命令

```powershell
$env:LOCAL_QUANT_PATH = "D:\Work Space\local_quant"
$env:HDATA_ROOT = "D:\Work Space\HData"

python tools/check_local_quant_compat.py `
  --local-quant-path "$env:LOCAL_QUANT_PATH" `
  --output "research/local_migration/compatibility_result.json"

python -m pytest tests/test_baseline_immutable.py tests/test_compatibility_inventory.py -q -s

git push origin research/local-port-v0
```

---

## 9. 测试结果

```
tests/test_baseline_immutable.py ........ 7/7 PASSED
tests/test_compatibility_inventory.py .... 25/25 PASSED

总计: 32 通过, 0 失败, 0 跳过
```

### 测试覆盖清单

| 测试名称 | 状态 | 说明 |
|---|---|---|
| `test_local_quant_path_must_resolve` | PASS | 路径解析正常 |
| `test_compat_script_runs` | PASS | 脚本可运行，退出码2 |
| `test_compat_script_exit_code_for_missing` | PASS | 存在MISSING时返回2 |
| `test_coverage_stats_consistent` | PASS | JSON统计一致 |
| `test_log_warn_detected_as_missing` | PASS | log.warn正确标记为MISSING |
| `test_log_warning_detected_as_present` | PASS | log.warning正确标记为PASS |
| `test_current_data_0930_last_price_uses_open` | PASS | 探针运行完成 |
| `test_511880_uses_etf_cost_model` | PASS | 真实Engine费用路由验证完成 |
| `test_minute_data_has_high_limit_for_check_limit_up` | PASS | 分钟数据high_limit验证完成 |

---

## 10. 新增/修改文件

```
research/local_migration/
├── API_COVERAGE.md                         # [修改] 统计修正
├── MIGRATION_GAPS.md                       # [修改] 新增GAP-012
├── compatibility_result.json               # [修改] 按修正脚本重新生成
└── reports/
    └── TASK-MICROCAP-001_REPORT.md         # [修改] 本报告

tools/
└── check_local_quant_compat.py             # [修改] 修复log.warn检测、路径解析、输出结构

tests/
└── test_compatibility_inventory.py         # [修改] 新增9个测试，修复SKIP→FAIL
```

---

## 11. 本地提交

| 提交 | 信息 |
|---|---|
| `ab5cec4` | research: add microcap local migration preflight |
| `0cadcc593d4a0a9e0d3bba8717a8cf5eaab29157` | research: correct microcap migration preflight audit |
| `35d7f844ac74a3346d4c3a451de97036357e11c4` | research: finalize microcap migration preflight evidence |
| `f5597f5ad8deebc79b299666216e2f879e977054` | research: close microcap preflight 001B |

---

## 12. 实证验证结果

### 09:30 价格语义（`test_current_data_0930_last_price_uses_open`）

| 项目 | 值 |
|---|---|
| 股票 | 000001.XSHE（平安银行） |
| 日期 | 2024-01-03 |
| 前收盘 | 9.21 |
| 当日开盘 | 9.19 |
| last_price | 9.19 |
| Engine验证 | last_price(9.19) == open(9.19) != pre_close(9.21) ✓ |

**结论**：GAP-005已关闭。local_quant在09:30正确返回当日开盘价。

### ETF 费用模型（`test_511880_uses_etf_cost_model`）

| 项目 | 策略设置值(type='stock') | ETF默认费用 |
|---|---|---|
| open_tax | 0 | 0 |
| close_tax | 0.001 | **0** |
| open_commission | 0.0001 | 0.0001 |
| close_commission | 0.0001 | 0.0001 |
| min_commission | 5 | **0** |

**结论**：GAP-008已关闭。Engine._order_costs有独立'etf'条目，不受type='stock'设置影响。ETF自动使用免印花税费用模型。

### 分钟数据 high_limit 验证（`test_minute_data_has_high_limit_for_check_limit_up`）

| 股票 | 年份 | 是否包含 high_limit | close | 索引≤14:00 |
|---|---|---|---|---|
| 000001.SZ | 2023 | 是(15.15) | 14.35 | ✓ |
| 000001.SZ | 2024 | 是(10.13) | 9.15 | ✓ |
| 000001.SZ | 2025 | 是(12.52) | 11.38 | ✓ |

**结论**：所有样本均包含high_limit且非空。14:00 `check_limit_up` 可正确获取该字段。UNKNOWN已消除。

---

## 13. 需要负责人裁决的问题

1. **P0 修复顺序**：GAP-001（position.value）最紧急（直接运行时异常）。GAP-012（log.warn）次之（与GAP-002/003/004有恶化交互）。建议在引擎中同时修复 5 个 P0。
2. **已关闭缺口**：GAP-005（09:30语义）和 GAP-008（ETF费用）经实证验证已确认兼容，不再需要修复或裁决。

---

## 14. 结论

**本任务已满足 TASK-MICROCAP-001B 验收标准 A-D。**

- 策略基线未修改（SHA-256 确认，git diff 干净）
- local_quant 未修改
- API 依赖已全面审计（38 项，逐项标注状态）
- 统计完全一致（JSON → API_COVERAGE.md → 报告三统一）
- 所有测试通过，0 失败，0 跳过
- 兼容性预检脚本正确返回退出码 2
- 实证探针消除 UNKNOWN（分钟数据 high_limit 确认存在）
- 新增 log.warn 缺失缺口（GAP-012）

**最终缺口清单**：5 P0（阻止运行）+ 2 P1（结果可能偏差）+ 3 P2（实盘真实性）
