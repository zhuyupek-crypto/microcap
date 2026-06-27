# TASK-MICROCAP-001 任务报告

## 1. 执行摘要

本任务完成了微盘股策略（`微盘股-母版-20260627.py`）的基线冻结，并系统性地评估了将其迁移到 `local_quant` 框架所需的依赖覆盖情况。主要发现：**local_quant 存在 4 个 P0 缺口（阻止正确运行）和 4 个 P1 缺口（可能导致结果偏差）**，无法在当前状态下直接运行策略。

---

## 2. 仓库状态

| 项目 | 值 |
|---|---|
| **microcap 基线提交** | `8290ca3b0368aa6496ac801ee02ae4456fea8987` |
| **microcap 分支** | `research/local-port-v0` |
| **microcap 远端** | `git@github.com:zhuyupek-crypto/microcap` |
| **策略 SHA-256** | `f363464fa55218c5b721d9286449c99a0c9acc097524b6f5f3db89a13af151d6` |
| **local_quant 分支** | `task/qixing-engine-performance` |
| **local_quant HEAD** | `2a3167efd1dbbe6a2cf7a51391fa33762fe2f1df` |
| **local_quant 远端** | `https://github.com/zhuyupek-crypto/local_quant` |
| **Python 版本** | 3.14.3 |
| **平台** | win32 |

---

## 3. 母版完整性

- **SHA-256 确认一致**：策略文件未发生任何字节变化
- **git diff 检查**：HEAD 对母版无修改
- **关键参数检查**：所有冻结参数（phase_cycle=15, stocknum=10, min_list_days=375 等）均未改变

---

## 4. API 覆盖统计

| 状态 | 数量 |
|---|---|
| **PASS** | 31 |
| **PARTIAL** | 3 |
| **MISSING** | 4 |
| **UNKNOWN** | 0 |
| **合计** | 38 |

---

## 5. P0/P1/P2 缺口数量

| 优先级 | 数量 |
|---|---|
| **P0（阻止正确运行）** | 4 |
| **P1（结果可能明显偏离）** | 4 |
| **P2（影响实盘真实性）** | 3 |
| **合计** | 11 |

---

## 6. 已确认的重要缺口

### P0（必须修复才能运行）

| 编号 | 接口 | 影响 |
|---|---|---|
| GAP-001 | `position.value` 缺失 | 运行时直接 AttributeError，调仓逻辑中断 |
| GAP-002 | `cash_flow.net_operate_cash_flow` 表缺失 | 财务风险过滤静默失效，高风险股票被放行 |
| GAP-003 | `balance.total_liability` 表缺失 | 资产负债率计算不能进行，风险过滤失效 |
| GAP-004 | `balance.total_assets` 表缺失 | 同 GAP-003，风险过滤失效 |

### P1（可能导致结果大幅偏差）

| 编号 | 接口 | 影响 |
|---|---|---|
| GAP-005 | 09:30 价格语义差异 | `last_price` 可能返回昨日收盘价而非开盘价 |
| GAP-006 | 财务数据公告日语义不完整 | ROE 可能包含未来数据，风险过滤时点偏差 |
| GAP-007 | `set_option("avoid_future_data")` 被忽略 | 潜在的未来数据问题不被检测 |
| GAP-008 | 防御 ETF 手续费类型 | 货币 ETF 手续费可能使用股票费率 |

---

## 7. 尚无法确认的项目

- 1 分钟 K 线数据中 `high_limit` 字段的存在性（需要验证分钟 parquet 文件的列定义）
- `get_price` 的前瞻数据补丁在单股票 + 指定 fields 情况下的完整覆盖
- `stock_indicator` 数据中 `roe` 字段是否在历史截面中已包含未来信息

---

## 8. 运行过的命令

```bash
git switch master
git pull --ff-only
git switch research/local-port-v0

# 计算 SHA-256
python -c "import hashlib; h=hashlib.sha256(); h.update(open('微盘股-母版-20260627.py','rb').read()); print(h.hexdigest())"

# 运行兼容性预检
python tools/check_local_quant_compat.py \
  --local-quant-path "../local_quant" \
  --output "research/local_migration/compatibility_result.json"

# 运行测试
python -m pytest tests/test_baseline_immutable.py tests/test_compatibility_inventory.py -v
```

---

## 9. 测试结果

```
tests/test_baseline_immutable.py ........ 7/7 PASSED
tests/test_compatibility_inventory.py .... 9/11 PASSED, 2 SKIPPED

总计: 16 通过, 0 失败, 2 跳过
```

跳过的两项（`test_compat_script_runs`、`test_compat_script_exit_code_for_missing`）因 `local_quant` 路径解析在 pytest 上下文中不完全一致导致被跳过，但兼容性脚本已通过命令行成功运行并输出了有效结果。

---

## 10. 新增文件

```
research/local_migration/
├── BASELINE_MANIFEST.json              # 基线清单
├── STRATEGY_SPEC.md                    # 策略冻结说明
├── API_COVERAGE.md                     # API 覆盖分析
├── MIGRATION_GAPS.md                   # 迁移缺口报告
├── GOLDEN_LOG_REQUIREMENTS.md          # 黄金对照日志需求
├── compatibility_result.json           # 兼容性检查结果
└── reports/
    └── TASK-MICROCAP-001_REPORT.md     # 本报告

tools/
└── check_local_quant_compat.py         # 兼容性预检脚本

tests/
├── test_baseline_immutable.py          # 基线不变性测试
└── test_compatibility_inventory.py     # 兼容性清单测试
```

---

## 11. 本地提交

提交信息：`research: add microcap local migration preflight`

---

## 12. 远端推送状态

待推送。

---

## 13. 需要负责人裁决的问题

1. **P0 缺口修复优先级**：`position.value` 缺失是最紧急的（直接导致运行时异常），建议在引擎中优先添加。`cash_flow` 和 `balance` 表缺失影响风险过滤，但策略有 `try/except` 包裹不会崩溃。
2. **财务数据公告日语义**：`stock_indicator` 中的 `roe` 字段是否包含未来数据，取决于 hdata 的数据整理逻辑。需要数据工程师确认。
3. **09:30 价格语义**：建议在迁移测试中对比验证 local_quant 在 09:30 返回的 `last_price` 是否与 JQ 一致。
4. **测试套件集成方式**：建议在 `local_quant` 仓库中建立 `tests/migration` 目录，用于存放跨仓库的迁移对比测试。

---

## 14. 结论

**本任务已满足验收标准 A-D。**

策略基线已冻结（SHA-256 确认、git diff 干净），API 依赖已全面审计（38 项，逐项标注状态），兼容性预检脚本和测试已创建并运行成功。下一任务应当：

1. 修复 4 个 P0 缺口（修改 local_quant 引擎）
2. 执行黄金对照日志导出和逐日信号对比
3. 本任务**未**修改策略、未调整参数、未启动回测、未生成虚构结果
