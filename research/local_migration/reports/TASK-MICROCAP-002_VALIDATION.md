# TASK-MICROCAP-002 本地验证报告

## 合规确认

- 冻结母版 SHA: f363464fa55218c5b721d9286449c99a0c9acc097524b6f5f3db89a13af151d6 ✓
- 未修改策略代码、参数或逻辑 ✓
- local_quant 修改仅限兼容层（core.py, context.py, data_api.py）✓

## 提交

| 仓库 | 分支 | SHA |
|---|---|---|
| local_quant | task/microcap-compat-v1 | 2ff7d76538d301452fdb5e243de2ae4e27abe251 |
| microcap | research/local-port-v0 | 本文件所在提交 |

## 兼容性预检

- 运行: `python tools/check_local_quant_compat.py --local-quant-path ../local_quant`
- 结果: PASS 37, PARTIAL 1 (set_benchmark), MISSING 0
- blocking_missing: [], blocking_partial: [], non_blocking_partial: ["set_benchmark"]
- 退出码: 0

## API_COVERAGE.md 正文同步完成

- get_fundamentals: 状态 PASS，删除旧 PARTIAL/P0 描述
- cash_flow.net_operate_cash_flow: 状态 PASS，删除"将抛出异常/风险过滤静默失效/P0"
- balance.total_liability: 状态 PASS，补充 PIT 实证证据
- balance.total_assets: 状态 PASS，补充 PIT 实证证据
- position.value: 状态 PASS，删除"将抛出 AttributeError/调仓异常中断/P0"
- 检查结果：仅 set_benchmark 为 PARTIAL，无残留 P0/MISSING/风险过滤失效描述

## MIGRATION_GAPS.md 正文同步完成

- 所有 P0 (GAP-001~004, 012) 均已标注 ~~已关闭~~，仅保留编号/原优先级/修复位置/关闭证据/关闭日期
- 所有 P1 (GAP-005~008) 均已标注 ~~已关闭~~
- 开放 P0=0, P1=0, P2=3 (GAP-009, 010, 011)
- 删除所有"当前行为：缺失/建议修复/将抛异常/风险过滤失效"旧描述

## 七星高照误提交文件已移除

从 local_quant task/microcap-compat-v1 分支移除以下 TASK-002 误提交文件：
- research/qixing_full_year_2024.py
- scripts/compare_parity_vs_jq.py
- scripts/debug_ranking.py
- scripts/debug_vol.py
- temp_screenshot1.png
- temp_screenshot_404.png

保留 projects/qixing/ 通用七星高照功能不受影响。

## 完整回归矩阵

完整 suite 不是简单 31 项专项测试，而是按文件逐文件执行+基线对比：

| 指标 | 值 |
|---|---|
| 测试文件总数 | 10 |
| 通过文件数 | 7 |
| 预存非阻塞文件数 | 3 |
| TASK-MICROCAP-002 新增失败数 | 0 |
| 专项测试 (3 文件聚合) | 31 passed |

### 预存慢测试清单

| 文件 | 基线结果 | 002 是否修改 |
|---|---|---|
| test_data_api.py (test_get_trade_days) | 基线同样断言失败 | 否 |
| test_order.py | 基线同样超时 | 否 |
| test_sample_strategy.py | 基线同样超时 | 否 |

基线提交: a579147 (此提交上 TASK-002 尚未开始)

## 运行验证

| 测试 | 日期范围 | 交易日 | 订单 | 错误 |
|---|---|---|---|---|
| 防御期 | 2024-01-02 ~ 2024-01-05 | 4 | 1 | 0 |
| 非防御期 | 2024-02-01 ~ 2024-02-29 | 15 | 79 | 0 |

## 开放项

P2 缺口 (不阻塞策略运行):
- GAP-009: 部分成交处理
- GAP-010: 市场冲击成本
- GAP-011: 连续跌停退出
