"""Compare 2020-only results: close fix vs previous r3_full slice."""
import pandas as pd

# 新结果（close 修复后，只跑 2020）
new_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_only_close_fix\trades.csv')
new_equity = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_only_close_fix\equity.csv')

# 旧结果（r3_full 的 2020 切片，close 修复前）
old_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\trades.csv')
old_equity = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\equity.csv')

# 切到 2020 年
old_trades['time'] = pd.to_datetime(old_trades['time'])
old_trades = old_trades[old_trades['time'].dt.year == 2020].copy()
# equity.csv uses 'date' column
_date_col = 'time' if 'time' in old_equity.columns else 'date'
old_equity[_date_col] = pd.to_datetime(old_equity[_date_col])
old_equity = old_equity[old_equity[_date_col].dt.year == 2020].copy()

print('=== 2020 年回测结果对比 ===')
print(f'{"指标":<25} {"修复前(r3_full切片)":<25} {"修复后(2020独立)":<25} {"差异":<15}')
print('-' * 90)

# fills
print(f'{"fills":<25} {len(old_trades):<25} {len(new_trades):<25} {len(new_trades) - len(old_trades):<15}')

# 期末资金
old_end = old_equity['value'].iloc[-1] if not old_equity.empty else None
new_end = new_equity['value'].iloc[-1] if not new_equity.empty else None
print(f'{"ending_value":<25} {old_end:<25.2f} {new_end:<25.2f} {new_end - old_end:<15.2f}')

# 起始资金
old_start = old_equity['value'].iloc[0] if not old_equity.empty else None
new_start = new_equity['value'].iloc[0] if not new_equity.empty else None
print(f'{"starting_value":<25} {old_start:<25.2f} {new_start:<25.2f} {new_start - old_start:<15.2f}')

# 收益率
old_ret = (old_end / old_start - 1) * 100 if old_start else None
new_ret = (new_end / new_start - 1) * 100 if new_start else None
print(f'{"total_return":<25} {old_ret:<25.4f}% {new_ret:<25.4f}% {new_ret - old_ret:<15.4f}%')

# 交易日数
print(f'{"trading_days":<25} {len(old_equity):<25} {len(new_equity):<25} {len(new_equity) - len(old_equity):<15}')

# 比较交易明细（前 10 笔差异）
print()
print('=== 交易差异（前 20 笔）===')
# 合并比较
old_trades['date'] = old_trades['time'].dt.strftime('%Y-%m-%d')
new_trades['time'] = pd.to_datetime(new_trades['time'])
new_trades['date'] = new_trades['time'].dt.strftime('%Y-%m-%d')

# 按 date+code+amount 比较
old_grp = old_trades.groupby(['date', 'code', 'amount']).size().reset_index(name='old_count')
new_grp = new_trades.groupby(['date', 'code', 'amount']).size().reset_index(name='new_count')

merged = old_grp.merge(new_grp, on=['date', 'code', 'amount'], how='outer').fillna(0)
diffs = merged[merged['old_count'] != merged['new_count']]
print(f'差异交易组数: {len(diffs)}')
if not diffs.empty:
    print(diffs.head(20).to_string())

# 价格差异
print()
print('=== 价格差异 ===')
# 按 date+code+amount 合并价格
old_price = old_trades.groupby(['date', 'code', 'amount'])['price'].first().reset_index()
new_price = new_trades.groupby(['date', 'code', 'amount'])['price'].first().reset_index()
price_cmp = old_price.merge(new_price, on=['date', 'code', 'amount'], how='inner', suffixes=('_old', '_new'))
price_diff = price_cmp[price_cmp['price_old'] != price_cmp['price_new']]
print(f'价格差异行数: {len(price_diff)}')
if not price_diff.empty:
    print(price_diff.head(20).to_string())
