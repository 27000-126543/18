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

    def benchmark_data_insert(self, num_equipments=1000, records_per_equipment=100,
                              num_threads=100, batch_size=100):
        """
        测试批量传感器数据插入性能
        :param num_equipments: 模拟设备数量
        :param records_per_equipment: 每台设备数据条数
        :param num_threads: 并发线程数
        :param batch_size: 每批插入条数
        """
        print("\n" + "=" * 70)
        print(f"  [压力测试 1] 传感器数据批量写入")
        print(f"  设备数: {num_equipments} | 每设备数据: {records_per_equipment} 条")
        print(f"  线程数: {num_threads} | 批量大小: {batch_size}")
        print(f"  总数据量: {num_equipments * records_per_equipment:,} 条")
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

        print(f"\n\n  ✓ 完成: 成功 {success:,} 条, 失败 {failed} 批次")
        print(f"  总耗时: {elapsed_total:.2f} 秒")
        print(f"  吞吐量: {success / elapsed_total:,.1f} 条/秒 (QPS)")
        if latencies:
            print(f"  延迟 P50: {statistics.median(latencies):.2f} ms/批")
            sorted_lat = sorted(latencies)
            p95_idx = int(len(sorted_lat) * 0.95)
            print(f"  延迟 P95: {sorted_lat[p95_idx]:.2f} ms/批")
            print(f"  平均延迟: {statistics.mean(latencies):.2f} ms/批")
        print(f"  错误数: {len(self.errors)}")
        if self.errors[:3]:
            print(f"  错误示例: {self.errors[:3]}")

        return {
            'test': 'data_insert',
            'qps': success / elapsed_total,
            'p50_ms': statistics.median(latencies) if latencies else 0,
            'p95_ms': sorted_lat[p95_idx] if latencies else 0,
            'total_records': success,
            'errors': len(self.errors),
            'elapsed_seconds': elapsed_total
        }

    def benchmark_query_performance(self, num_queries=1000, num_threads=20):
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

        print(f"\n\n  ✓ 完成: 成功 {success} 次, 失败 {failed} 次")
        print(f"  总耗时: {elapsed_total:.2f} 秒")
        print(f"  吞吐量: {success / elapsed_total:,.1f} QPS")
        if latencies:
            print(f"  延迟 P50: {statistics.median(latencies):.2f} ms")
            sorted_lat = sorted(latencies)
            p95_idx = min(len(sorted_lat) - 1, int(len(sorted_lat) * 0.95))
            print(f"  延迟 P95: {sorted_lat[p95_idx]:.2f} ms")
            print(f"  延迟 P99: {sorted_lat[min(len(sorted_lat)-1, int(len(sorted_lat)*0.99))]:.2f} ms")
            print(f"  平均延迟: {statistics.mean(latencies):.2f} ms")

        return {
            'test': 'query',
            'qps': success / elapsed_total,
            'p50_ms': statistics.median(latencies) if latencies else 0,
            'p95_ms': sorted_lat[p95_idx] if latencies else 0,
            'total_queries': success,
            'errors': failed,
            'elapsed_seconds': elapsed_total
        }

    def benchmark_concurrent_read_write(self, duration_seconds=30, read_threads=30, write_threads=20):
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

    def run_full_suite(self):
        """运行完整压力测试套件"""
        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 15 + "制造业预测性维护系统 - 高并发压力测试" + " " * 16 + "║")
        print("╚" + "═" * 68 + "╝")

        init_database()

        all_results = []
        try:
            r1 = self.benchmark_data_insert(
                num_equipments=500,
                records_per_equipment=200,
                num_threads=80,
                batch_size=200
            )
            all_results.append(r1)

            r2 = self.benchmark_query_performance(num_queries=2000, num_threads=30)
            all_results.append(r2)

            r3 = self.benchmark_concurrent_read_write(duration_seconds=20, read_threads=20, write_threads=15)
            all_results.append(r3)

        except Exception as e:
            logger.error(f"压力测试出错: {e}")
            print(f"\n压力测试异常: {e}")

        print("\n" + "=" * 70)
        print("  📊 压力测试汇总报告")
        print("=" * 70)
        for r in all_results:
            print(f"\n  [{r['test']}]")
            for k, v in r.items():
                if k != 'test':
                    if isinstance(v, float):
                        print(f"    {k}: {v:,.2f}")
                    else:
                        print(f"    {k}: {v:,}")

        report_path = os.path.join('reports', f'stress_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        os.makedirs('reports', exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"\n  📄 详细报告已保存至: {report_path}")

        target_daily = 200000
        est_daily_capacity = 0
        for r in all_results:
            if r['test'] == 'data_insert':
                est_daily_capacity = r['qps'] * 86400
                print(f"\n  🎯 目标日吞吐量: {target_daily:,} 条/天")
                print(f"  📈 理论日吞吐量: {est_daily_capacity:,.0f} 条/天")
                ratio = est_daily_capacity / target_daily * 100
                print(f"  ✅ 达成率: {ratio:.1f}% {'(达标 ✓)' if ratio >= 100 else '(未达标 ✗)'}")
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
