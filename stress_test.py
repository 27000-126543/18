#!/usr/bin/env python3
"""
高并发压力测试脚本
模拟数千台设备每天数十万条传感器数据点的采集与分析
支持: 批量数据写入、健康评估、数据库压力测试
输出: QPS、P50/P95延迟、错误率、吞吐量报告
"""

import sys
import os
import time
import random
import math
import sqlite3
import threading
import statistics
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_db_cursor, get_connection
from core.logger import logger
from utils.helpers import now_str
from models.schema import init_database


def percentile(data, p, max_samples=100000):
    """
    计算分位数（p: 0-100）
    当数据量超过max_samples时，采用系统抽样防止内存撑爆和排序过慢
    """
    if not data:
        return 0.0
    n = len(data)
    if n <= max_samples:
        sampled = data
    else:
        step = n // max_samples
        sampled = [data[i] for i in range(0, n, step)]
    sorted_data = sorted(sampled)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


class StressTester:
    def __init__(self):
        self.results = defaultdict(list)
        self.errors = []
        self.lock = threading.Lock()
        self.total_records = 0

    def simulate_sensor_data(self, equipment_id, baseline=None):
        """模拟生成一条真实的传感器数据"""
        baseline = baseline or {
            'temp_base': 55.0, 'temp_std': 3.0,
            'vib_base': 3.0, 'vib_std': 0.5,
            'curr_base': 12.0, 'curr_std': 1.0
        }
        anomaly_chance = random.random() < 0.05
        temp = baseline['temp_base'] + random.gauss(0, baseline['temp_std'])
        vibration = baseline['vib_base'] + random.gauss(0, baseline['vib_std'])
        current = baseline['curr_base'] + random.gauss(0, baseline['curr_std'])
        if anomaly_chance:
            factor = random.choice([1.5, 2.0, 2.5])
            temp *= factor
            vibration *= factor
        is_anomaly = 1 if (temp > baseline['temp_base'] + 2 * baseline['temp_std'] or
                           vibration > baseline['vib_base'] + 2 * baseline['vib_std']) else 0
        return {
            'equipment_id': equipment_id,
            'temperature': round(temp, 2),
            'vibration': round(vibration, 3),
            'current': round(current, 2),
            'is_anomaly': is_anomaly,
            'collection_time': now_str()
        }

    def benchmark_data_insert(self, num_equipments=200, records_per_equipment=100,
                              num_threads=50, batch_size=200):
        """
        测试批量传感器数据插入性能
        :param num_equipments: 模拟设备数量
        :param records_per_equipment: 每台设备数据条数
        :param num_threads: 并发线程数
        :param batch_size: 每批插入条数
        """
        total = num_equipments * records_per_equipment
        print("\n" + "=" * 70)
        print(f"  [压力测试 1] 传感器数据批量写入")
        print(f"  设备数: {num_equipments:,} 台 | 每设备: {records_per_equipment:,} 条/天")
        print(f"  线程数: {num_threads} | 批量大小: {batch_size}")
        print(f"  总数据量: {total:,} 条 (约{total/10000:.1f}万)")
        if num_equipments >= 2000 and records_per_equipment >= 500:
            print(f"  生产级目标: 2000台×500条=100万点/天 ✓")
        print("=" * 70)

        total_records = num_equipments * records_per_equipment
        baselines = {eid: {
            'temp_base': random.uniform(45, 70),
            'temp_std': random.uniform(2, 5),
            'vib_base': random.uniform(2, 6),
            'vib_std': random.uniform(0.3, 1.0),
            'curr_base': random.uniform(8, 18),
            'curr_std': random.uniform(0.5, 2.0)
        } for eid in range(1, num_equipments + 1)}

        def insert_batch(batch):
            start = time.perf_counter()
            try:
                with get_db_cursor(commit=True) as cursor:
                    cursor.executemany("""
                        INSERT INTO sensor_data
                        (equipment_id, temperature, vibration, current, is_anomaly, collection_time)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, [(d['equipment_id'], d['temperature'], d['vibration'],
                           d['current'], d['is_anomaly'], d['collection_time']) for d in batch])
                elapsed = (time.perf_counter() - start) * 1000
                with self.lock:
                    self.results['insert_latency_ms'].append(elapsed)
                    self.total_records += len(batch)
                return True, len(batch)
            except Exception as e:
                with self.lock:
                    self.errors.append(str(e))
                return False, 0

        all_data = []
        for eid in range(1, num_equipments + 1):
            for _ in range(records_per_equipment):
                all_data.append(self.simulate_sensor_data(eid, baselines.get(eid)))

        random.shuffle(all_data)
        batches = [all_data[i:i + batch_size] for i in range(0, len(all_data), batch_size)]

        start_time = time.perf_counter()
        success = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(insert_batch, b): i for i, b in enumerate(batches)}
            done = 0
            for fut in as_completed(futures):
                ok, count = fut.result()
                if ok:
                    success += count
                else:
                    failed += 1
                done += 1
                if done % 50 == 0:
                    pct = done / len(batches) * 100
                    print(f"  进度: {done}/{len(batches)} 批次 ({pct:.1f}%) - 已写入 {self.total_records:,} 条", end='\r')

        elapsed_total = time.perf_counter() - start_time
        latencies = self.results.get('insert_latency_ms', [])

        qps = success / elapsed_total if elapsed_total > 0 else 0
        print(f"\n\n  ✓ 完成: 成功 {success:,} 条, 失败 {failed} 批次")
        print(f"  总耗时: {elapsed_total:.2f} 秒")
        print(f"  吞吐量: {qps:,.1f} 条/秒 (QPS)")
        if latencies:
            p50 = percentile(latencies, 50)
            p90 = percentile(latencies, 90)
            p95 = percentile(latencies, 95)
            p99 = percentile(latencies, 99)
            avg_lat = statistics.mean(latencies)
            print(f"  ┌─────────────────────────────────────┐")
            print(f"  │  延迟分位统计 (每批{batch_size}条)        │")
            print(f"  ├─────────────────────────────────────┤")
            print(f"  │  P50 中位数 : {p50:>8.2f} ms            │")
            print(f"  │  P90        : {p90:>8.2f} ms            │")
            print(f"  │  P95        : {p95:>8.2f} ms            │")
            print(f"  │  P99        : {p99:>8.2f} ms            │")
            print(f"  │  平均延迟    : {avg_lat:>8.2f} ms            │")
            print(f"  └─────────────────────────────────────┘")
        print(f"  错误数: {len(self.errors)}")
        if self.errors[:3]:
            print(f"  错误示例: {self.errors[:3]}")

        return {
            'test': 'data_insert',
            'qps': qps,
            'p50_ms': p50 if latencies else 0,
            'p90_ms': p90 if latencies else 0,
            'p95_ms': p95 if latencies else 0,
            'p99_ms': p99 if latencies else 0,
            'avg_latency_ms': statistics.mean(latencies) if latencies else 0,
            'total_records': success,
            'errors': len(self.errors),
            'elapsed_seconds': elapsed_total,
            'num_equipments': num_equipments,
            'records_per_equipment': records_per_equipment,
            'test_daily_volume': num_equipments * records_per_equipment,
            'target_daily': 1000000,
            'estimated_daily': qps * 86400
        }

    def benchmark_query_performance(self, num_queries=500, num_threads=10):
        """
        测试数据库查询性能
        """
        print("\n" + "=" * 70)
        print(f"  [压力测试 2] 数据库查询性能")
        print(f"  查询次数: {num_queries} | 线程数: {num_threads}")
        print("=" * 70)

        query_templates = [
            ("SELECT COUNT(*) FROM sensor_data", [], "count_total"),
            ("SELECT * FROM sensor_data WHERE equipment_id = ? ORDER BY collection_time DESC LIMIT 100",
             [random.randint(1, 500)], "recent_sensor"),
            ("SELECT * FROM equipments WHERE status = 'active'", [], "active_equipments"),
            ("SELECT AVG(temperature), AVG(vibration) FROM sensor_data WHERE equipment_id = ? AND collection_time > ?",
             [random.randint(1, 500), (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')],
             "sensor_7day_avg"),
            ("SELECT status, COUNT(*) FROM work_orders GROUP BY status", [], "wo_stats"),
        ]

        def run_query():
            start = time.perf_counter()
            try:
                q_template, params, _ = random.choice(query_templates)
                if '?' in q_template:
                    p = [random.randint(1, 500) if 'equipment_id' in q_template else v for v in params]
                else:
                    p = params
                with get_db_cursor() as cursor:
                    cursor.execute(q_template, p)
                    cursor.fetchall()
                elapsed = (time.perf_counter() - start) * 1000
                with self.lock:
                    self.results['query_latency_ms'].append(elapsed)
                return True
            except Exception as e:
                with self.lock:
                    self.errors.append(str(e))
                return False

        self.results['query_latency_ms'] = []
        self.errors = []

        start_time = time.perf_counter()
        success = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(run_query) for _ in range(num_queries)]
            for i, fut in enumerate(as_completed(futures)):
                if fut.result():
                    success += 1
                else:
                    failed += 1
                if (i + 1) % 100 == 0:
                    print(f"  进度: {i+1}/{num_queries} ({(i+1)/num_queries*100:.1f}%)", end='\r')

        elapsed_total = time.perf_counter() - start_time
        latencies = self.results.get('query_latency_ms', [])
        qps = success / elapsed_total if elapsed_total > 0 else 0

        print(f"\n\n  ✓ 完成: 成功 {success} 次, 失败 {failed} 次")
        print(f"  总耗时: {elapsed_total:.2f} 秒")
        print(f"  吞吐量: {qps:,.1f} QPS")
        if latencies:
            p50 = percentile(latencies, 50)
            p90 = percentile(latencies, 90)
            p95 = percentile(latencies, 95)
            p99 = percentile(latencies, 99)
            avg_lat = statistics.mean(latencies)
            print(f"  ┌─────────────────────────────────────┐")
            print(f"  │  查询延迟分位统计                      │")
            print(f"  ├─────────────────────────────────────┤")
            print(f"  │  P50 中位数 : {p50:>8.2f} ms            │")
            print(f"  │  P90        : {p90:>8.2f} ms            │")
            print(f"  │  P95        : {p95:>8.2f} ms            │")
            print(f"  │  P99        : {p99:>8.2f} ms            │")
            print(f"  │  平均延迟    : {avg_lat:>8.2f} ms            │")
            print(f"  └─────────────────────────────────────┘")

        return {
            'test': 'query',
            'qps': qps,
            'p50_ms': p50 if latencies else 0,
            'p90_ms': p90 if latencies else 0,
            'p95_ms': p95 if latencies else 0,
            'p99_ms': p99 if latencies else 0,
            'avg_latency_ms': statistics.mean(latencies) if latencies else 0,
            'total_queries': success,
            'errors': failed,
            'elapsed_seconds': elapsed_total
        }

    def benchmark_concurrent_read_write(self, duration_seconds=10, read_threads=10, write_threads=5):
        """
        测试同时读写的并发性能
        """
        print("\n" + "=" * 70)
        print(f"  [压力测试 3] 混合读写并发 ({duration_seconds}秒)")
        print(f"  读线程: {read_threads} | 写线程: {write_threads}")
        print("=" * 70)

        stop_event = threading.Event()
        counters = {'read': 0, 'write': 0, 'read_err': 0, 'write_err': 0}
        counter_lock = threading.Lock()

        def writer_loop():
            conn = get_connection()
            while not stop_event.is_set():
                try:
                    eid = random.randint(1, 500)
                    d = self.simulate_sensor_data(eid)
                    conn.execute("""
                        INSERT INTO sensor_data (equipment_id, temperature, vibration, current, is_anomaly, collection_time)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (d['equipment_id'], d['temperature'], d['vibration'],
                          d['current'], d['is_anomaly'], d['collection_time']))
                    conn.commit()
                    with counter_lock:
                        counters['write'] += 1
                except Exception:
                    with counter_lock:
                        counters['write_err'] += 1

        def reader_loop():
            while not stop_event.is_set():
                try:
                    with get_db_cursor() as cursor:
                        eid = random.randint(1, 500)
                        cursor.execute("""
                            SELECT AVG(temperature), AVG(vibration)
                            FROM sensor_data WHERE equipment_id = ?
                            ORDER BY collection_time DESC LIMIT 1000
                        """, (eid,))
                        cursor.fetchone()
                    with counter_lock:
                        counters['read'] += 1
                except Exception:
                    with counter_lock:
                        counters['read_err'] += 1

        start_time = time.perf_counter()

        threads = []
        for _ in range(write_threads):
            t = threading.Thread(target=writer_loop, daemon=True)
            t.start()
            threads.append(t)
        for _ in range(read_threads):
            t = threading.Thread(target=reader_loop, daemon=True)
            t.start()
            threads.append(t)

        for i in range(duration_seconds):
            time.sleep(1)
            with counter_lock:
                r, w = counters['read'], counters['write']
            print(f"  {i+1}/{duration_seconds}s - 读: {r:,} ({r/(i+1):,.0f}/s) | 写: {w:,} ({w/(i+1):,.0f}/s)", end='\r')

        stop_event.set()
        for t in threads:
            t.join(timeout=5)

        elapsed = time.perf_counter() - start_time
        print(f"\n\n  ✓ 测试完成")
        print(f"  读操作: {counters['read']:,} ({counters['read']/elapsed:,.1f}/s) - 错误: {counters['read_err']}")
        print(f"  写操作: {counters['write']:,} ({counters['write']/elapsed:,.1f}/s) - 错误: {counters['write_err']}")
        print(f"  总吞吐: {(counters['read']+counters['write'])/elapsed:,.1f} ops/秒")

        return {
            'test': 'read_write_mix',
            'read_qps': counters['read'] / elapsed,
            'write_qps': counters['write'] / elapsed,
            'total_ops': counters['read'] + counters['write'],
            'read_errors': counters['read_err'],
            'write_errors': counters['write_err'],
            'duration_seconds': elapsed
        }

    def run_full_suite(self, small_scale=True):
        """
        运行完整压力测试套件
        :param small_scale: True=小规模快速测试(默认), False=生产级100万点/天全量测试
        """
        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 13 + "制造业预测性维护系统 - 高并发压力测试 v2.1" + " " * 13 + "║")
        print("╚" + "═" * 68 + "╝")
        print()
        if small_scale:
            print("  模式: 小规模快速验证 (small_scale=True)")
            print("  说明: 如需运行生产级100万点/天全量测试，请传入 small_scale=False")
            eq_num, rpe, threads, batch = 200, 100, 50, 200
            q_num, q_threads = 500, 10
            rw_dur, r_th, w_th = 10, 10, 5
            target_daily = eq_num * rpe
        else:
            print("  模式: 生产级全量测试 (small_scale=False)")
            print("  目标量级: 2,000台设备 × 500点/天 = 1,000,000条/天 (100万点/天)")
            eq_num, rpe, threads, batch = 2000, 500, 200, 500
            q_num, q_threads = 5000, 50
            rw_dur, r_th, w_th = 30, 50, 30
            target_daily = 1000000
        print("  输出指标: QPS吞吐量 | P50/P90/P95/P99延迟分位 | 错误率")

        init_database()

        all_results = []
        try:
            r1 = self.benchmark_data_insert(
                num_equipments=eq_num,
                records_per_equipment=rpe,
                num_threads=threads,
                batch_size=batch
            )
            all_results.append(r1)

            r2 = self.benchmark_query_performance(num_queries=q_num, num_threads=q_threads)
            all_results.append(r2)

            r3 = self.benchmark_concurrent_read_write(duration_seconds=rw_dur, read_threads=r_th, write_threads=w_th)
            all_results.append(r3)

        except Exception as e:
            logger.error(f"压力测试出错: {e}")
            print(f"\n压力测试异常: {e}")

        print("\n" + "=" * 70)
        print("  📊 压力测试汇总报告")
        print("=" * 70)
        for r in all_results:
            print(f"\n  ═══ [{r['test']}] ═══")
            for k, v in r.items():
                if k != 'test':
                    if isinstance(v, float):
                        print(f"    {k:25s}: {v:>12,.2f}")
                    else:
                        print(f"    {k:25s}: {v:>12,}")

        report_path = os.path.join('reports', f'stress_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        os.makedirs('reports', exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"\n  📄 详细JSON报告已保存至: {report_path}")

        est_daily_capacity = 0
        for r in all_results:
            if r['test'] == 'data_insert':
                est_daily_capacity = r['qps'] * 86400
                ratio = est_daily_capacity / target_daily * 100 if target_daily > 0 else 0
                status = '(达标 ✓)' if ratio >= 100 else '(未达标 ✗)'
                print()
                print(f"  ┌─────────────────────────────────────────────────────┐")
                print(f"  │  🎯 目标日吞吐量:  {target_daily:>12,} 条/天            │")
                print(f"  │  📈 理论日吞吐量:  {est_daily_capacity:>12,.0f} 条/天        │")
                print(f"  │  📊 达成率:        {ratio:>11.1f}% {status}         │")
                print(f"  └─────────────────────────────────────────────────────┘")
                break

        print("\n" + "=" * 70)
        return all_results


def main():
    tester = StressTester()
    try:
        tester.run_full_suite()
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(0)


if __name__ == '__main__':
    main()
