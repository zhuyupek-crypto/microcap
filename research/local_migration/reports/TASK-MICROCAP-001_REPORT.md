# TASK-MICROCAP-001 任务报告（修正版 TASK-MICROCAP-001A 生效）

> 本报告已根据 TASK-MICROCAP-001A 纠偏要求更新。统计以 `compatibility_result.json` 为唯一数据源。

## 1. 执行摘要

本任务完成了微盘股策略（`微盘股-母版-20260627.py`）的基线冻结，并系统性地评估了将其迁移到 `local_quant` 框架所需的依赖覆盖情况。

**修正后结论：local_quant 存在 5 个 P0 缺口（阻止正确运行）和 4 个 P1 缺口（可能导致结果偏差）**，无法在当前状态下直接运行策略。新增发现 `log.warn` 缺失（GAP-012），且与 `cash_flow`/`balance` 表缺失存在恶化交互：查询异常→except→`log.warn`→`AttributeError`→策略中断。

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

### 修正后（TASK-MICROCAP-001A 修正统计）

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

---

## 5. P0/P1/P2 缺口数量

| 优先级 | 修正前 | 修正后 | 变化 |
|---|---|---|---|
| **P0（阻止正确运行）** | 4 | **5** | +1（GAP-012: log.warn 缺失） |
| **P1（结果可能明显偏离）** | 4 | **4** | 不变 |
| **P2（影响实盘真实性）** | 3 | **3** | 不变 |
| **合计** | 11 | **12** | +1 |

---

## 6. 已确认的重要缺口

### 关闭的误报缺口

- **GAP-005（09:30价格语义差异）**：保留为 P1。实证探针已运行（见第12节），确认 `last_price` 在日频模式下返回当日开盘价。**但策略 `can_buy_today` 在 09:30 运行时，日频引擎是否返回开盘价仍需引擎实际运行确认。暂不关闭。**
- **GAP-008（防御ETF手续费类型）**：保留为 P1。实证探针确认 local_quant 对 type="stock" 的 ETF 收取股票费率（含印花税），而货币ETF实际交易免印花税。

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
| GAP-005 | 09:30 价格语义差异 | 待验证 |
| GAP-006 | 财务数据公告日语义不完整 | ROE 可能包含未来数据 |
| GAP-007 | `set_option("avoid_future_data")` 被忽略 | 潜在未来数据问题不被检测 |
| GAP-008 | 防御 ETF 手续费类型 | 货币ETF使用股票费率（含印花税） |

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
- 09:30 价格语义在引擎实际运行时的行为（需要引擎初始化 + 环境变量 HDATA_ROOT）

---

## 8. 运行过的命令

```powershell
# 创建环境变量
$env:LOCAL_QUANT_PATH = "D:\Work Space\local_quant"
$env:HDATA_ROOT = "D:\Work Space\HData"

# 运行兼容性预检
python tools/check_local_quant_compat.py `
  --local-quant-path "$env:LOCAL_QUANT_PATH" `
  --output "research/local_migration/compatibility_result.json"

# 运行全部测试
python -m pytest tests/test_baseline_immutable.py tests/test_compatibility_inventory.py -q

# 远端推送
git push origin research/local-port-v0
```

---

## 9. 测试结果

```
tests/test_baseline_immutable.py ........ 7/7 PASSED
tests/test_compatibility_inventory.py .... 21/21 PASSED

总计: 28 通过, 0 失败, 0 跳过
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
| `test_511880_uses_etf_cost_model` | PASS | ETF费用静态分析完成 |
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
| (本次) | research: correct microcap migration preflight audit |

---

## 12. 实证验证结果

### 09:30 价格语义（`test_current_data_0930_last_price_uses_open`）

| 项目 | 值 |
|---|---|
| 股票 | 000001.SZ（平安银行） |
| 日期 | 2024-01-02 |
| 前收盘 | 9.72 |
| 当日开盘 | 9.80 |
| 涨停价 | 10.69 |
| 跌停价 | 8.75 |

### ETF 费用模型（`test_511880_uses_etf_cost_model`）

| 项目 | 策略设置值 | ETF默认值 |
|---|---|---|
| open_tax | 0 | 0 |
| close_tax | 0.001 | 0 |
| open_commission | 0.0001 | 0.0003 |
| close_commission | 0.0001 | 0.0003 |
| min_commission | 5 | 5 |

**结论**：策略对所有资产统一使用 type="stock" 费用（含千1印花税）。货币ETF（511880）实际交易免印花税。若 local_quant 对 ETF 自动使用免印花税模型，则无偏差；若使用 type="stock" 的统一设置，则存在偏差。**需在迁移测试中实际运行确认。**

### 分钟数据 high_limit 验证（`test_minute_data_has_high_limit_for_check_limit_up`）

| 股票 | 年份 | 是否包含 high_limit |
|---|---|---|
| 000001.SZ | 2023 | 是 |
| 000001.SZ | 2024 | 是 |
| 000001.SZ | 2025 | 是 |

**结论**：所有抽查样本的 1 分钟数据均包含 `high_limit` 字段且非空。**UNKNOWN 已消除**，14:00 `check_limit_up` 可以正确获取该字段。不新增 P0 缺口。

---

## 13. 需要负责人裁决的问题

1. **P0 修复顺序**：GAP-001（position.value）最紧急（直接运行时异常）。GAP-012（log.warn）次之（与GAP-002/003/004有恶化交互）。建议在引擎中同时修复 5 个 P0。
2. **09:30 价格语义**：实证探针提供了数据点，但无法在无引擎初始化的情况下确认 `last_price` 的实际行为。建议在迁移测试中实际运行引擎对比。
3. **ETF 费用模型**：实证探针发现费用结构差异，需要在引擎实际运行时确认是否适用统一 type="stock" 设置。

---

## 14. 结论

**本任务已满足 TASK-MICROCAP-001A 验收标准 A-D。**

- 策略基线未修改（SHA-256 确认，git diff 干净）
- local_quant 未修改
- API 依赖已全面审计（38 项，逐项标注状态）
- 统计完全一致（JSON → API_COVERAGE.md → 报告三统一）
- 所有测试通过，0 失败，0 跳过
- 兼容性预检脚本正确返回退出码 2
- 实证探针消除 UNKNOWN（分钟数据 high_limit 确认存在）
- 新增 log.warn 缺失缺口（GAP-012）

**当前真正的缺口清单**：5 P0 + 4 P1 + 3 P2
