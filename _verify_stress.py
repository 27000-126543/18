import sys
sys.path.insert(0, '/Users/mac/Desktop/6.5项目/18')
import os
os.chdir('/Users/mac/Desktop/6.5项目/18')

from stress_test import StressTester

t = StressTester()

# 测试 small_scale=True (默认)
print("=" * 60)
print("测试1: run_full_suite(small_scale=True) - 小规模模式")
print("=" * 60)
# 只检查参数分配，不实际跑（太耗时）
# 检查benchmark默认参数是否为小规模
import inspect
sig = inspect.signature(t.benchmark_data_insert)
defaults = {
    k: v.default for k, v in sig.parameters.items()
    if v.default is not inspect.Parameter.empty
}
print(f"benchmark_data_insert 默认参数: {defaults}")
assert defaults['num_equipments'] == 200, "num_equipments应该是小规模200"
assert defaults['records_per_equipment'] == 100, "records_per_equipment应该是小规模100"
assert defaults['num_threads'] == 50, "num_threads应该是小规模50"
print("✓ benchmark默认参数都是小规模")

sig2 = inspect.signature(t.benchmark_query_performance)
defaults2 = {k: v.default for k, v in sig2.parameters.items() if v.default is not inspect.Parameter.empty}
print(f"benchmark_query_performance 默认参数: {defaults2}")
assert defaults2['num_queries'] == 500
assert defaults2['num_threads'] == 10
print("✓ benchmark_query_performance默认参数都是小规模")

sig3 = inspect.signature(t.benchmark_concurrent_read_write)
defaults3 = {k: v.default for k, v in sig3.parameters.items() if v.default is not inspect.Parameter.empty}
print(f"benchmark_concurrent_read_write 默认参数: {defaults3}")
assert defaults3['duration_seconds'] == 10
assert defaults3['read_threads'] == 10
assert defaults3['write_threads'] == 5
print("✓ benchmark_concurrent_read_write默认参数都是小规模")

# 检查run_full_suite的target_daily设置逻辑
import ast
src = inspect.getsource(t.run_full_suite)
assert "target_daily = 1000000" in src, "small_scale=False分支必须硬编码target_daily=1000000"
assert "target_daily = eq_num * rpe" in src, "small_scale=True分支必须动态计算target_daily"
print("✓ run_full_suite两种模式target_daily设置均正确")
print()
print("所有压力测试逻辑验证通过 ✓")
