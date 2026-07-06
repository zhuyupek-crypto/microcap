"""Compare r3_2020_pre_close_fix (HEAD order.py, close fix REVERTED) vs
r3_2020_only_close_fix (close fix APPLIED).

Both runs have Fallback 4 in data_api.py. The ONLY difference is order.py's
close fix. This isolates the close fix's actual effect.
"""
import pandas as pd

# close 修复前（HEAD order.py，field='avg' fallback to open）
pre_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_pre_close_fix\trades.csv')
pre_equity = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_pre_close_fix\equity.csv')

# close 修复后（current order.py，field='close'）
post_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_only_close_fix\trades.csv')
post_equity = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_only_close_fix\equity.csv')

pre_trades['time'] = pd.to_datetime(pre_trades['time'])
post_trades['time'] = pd.to_datetime(post_trades['time'])

print('=== 2020 close 修复前 vs 修复后（仅 order.py 差异）===')
print(f'{"指标":<25} {"修复前(pre_close_fix)":<25} {"修复后(close_fix)":<25} {"差异":<15}')
print('-' * 90)

print(f'{"fills":<25} {len(pre_trades):<25} {len(post_trades):<25} {len(post_trades) - len(pre_trades):<15}')

pre_end = pre_equity['value'].iloc[-1]
post_end = post_equity['value'].iloc[-1]
print(f'{"ending_value":<25} {pre_end:<25.2f} {post_end:<25.2f} {post_end - pre_end:<15.2f}')

pre_start = pre_equity['value'].iloc[0]
post_start = post_equity['value'].iloc[0]
print(f'{"starting_value":<25} {pre_start:<25.2f} {post_start:<25.2f} {post_start - pre_start:<15.2f}')

pre_ret = (pre_end / pre_start - 1) * 100
post_ret = (post_end / post_start - 1) * 100
print(f'{"total_return":<25} {pre_ret:<25.4f}% {post_ret:<25.4f}% {post_ret - pre_ret:<15.4f}%')

# 价格差异
print()
print('=== 价格差异（按 time+code+amount 对齐）===')
pre_trades['date'] = pre_trades['time'].dt.strftime('%Y-%m-%d')
post_trades['date'] = post_trades['time'].dt.strftime('%Y-%m-%d')

pre_price = pre_trades.groupby(['date', 'code', 'amount'])['price'].first().reset_index()
post_price = post_trades.groupby(['date', 'code', 'amount'])['price'].first().reset_index()
price_cmp = pre_price.merge(post_price, on=['date', 'code', 'amount'], how='inner', suffixes=('_pre', '_post'))
price_diff = price_cmp[abs(price_cmp['price_pre'] - price_cmp['price_post']) > 0.005]
print(f'价格差异行数: {len(price_diff)} / {len(price_cmp)}')
if not price_diff.empty:
    print(price_diff.head(20).to_string())

# 14:00 交易价格对比
print()
print('=== 14:00 交易价格对比 ===')
pre_14h = pre_trades[pre_trades['time'].dt.strftime('%H:%M') == '14:00'].copy()
post_14h = post_trades[post_trades['time'].dt.strftime('%H:%M') == '14:00'].copy()
print(f'pre 14:00 trades: {len(pre_14h)}, post 14:00 trades: {len(post_14h)}')

# 按 time+code 对齐
pre_14h_key = pre_14h.set_index(['time', 'code'])['price']
post_14h_key = post_14h.set_index(['time', 'code'])['price']
aligned = pre_14h_key.to_frame('pre_price').join(post_14h_key.to_frame('post_price'), how='inner')
aligned['diff'] = (aligned['post_price'] - aligned['pre_price']).abs()
diff_14h = aligned[aligned['diff'] > 0.005]
print(f'14:00 价格差异: {len(diff_14h)} / {len(aligned)}')
if not diff_14h.empty:
    print(diff_14h.head(20).to_string())

# 交易差异
print()
print('=== 交易差异（按 date+code+amount 对齐）===')
pre_grp = pre_trades.groupby(['date', 'code', 'amount']).size().reset_index(name='pre_count')
post_grp = post_trades.groupby(['date', 'code', 'amount']).size().reset_index(name='post_count')
merged = pre_grp.merge(post_grp, on=['date', 'code', 'amount'], how='outer').fillna(0)
diffs = merged[merged['pre_count'] != merged['post_count']]
print(f'差异交易组数: {len(diffs)}')
if not diffs.empty:
    print(diffs.head(20).to_string())
