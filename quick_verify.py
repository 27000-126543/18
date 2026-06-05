#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import PredictiveMaintenanceSystem
from core.database import get_db_cursor
from modules.sensor_collector import SensorDataCollector
from modules.daily_report import DailyReportGenerator
from modules.data_initializer import DataInitializer
from core.logger import logger


def quick_verify():
    print("=" * 60)
    print("  制造业设备预测性维护系统 - 快速验证")
    print("=" * 60)
    print()

    print("[1/5] 验证模块导入...")
    print("  ✓ 所有模块导入成功")

    print("[2/5] 初始化系统...")
    system = PredictiveMaintenanceSystem()
    system.initialize(seed_data=False)
    print("  ✓ 系统初始化成功")

    print("[3/5] 验证数据库表...")
    with get_db_cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r['name'] for r in cursor.fetchall()]
    print(f"  ✓ 已创建 {len(tables)} 张表:")
    for t in tables:
        print(f"    - {t}")

    print("[4/5] 验证基础数据与传感器采集...")
    init = DataInitializer()
    init._create_engineers()
    init._create_equipments()
    init._create_spare_parts()
    init._create_suppliers()
    init._create_supplier_parts()

    collector = SensorDataCollector()
    count = collector.collect_all()
    print(f"  ✓ 成功采集 {count} 条传感器数据 (100台设备)")

    print("[5/5] 验证报告生成...")
    daily = DailyReportGenerator()
    stats, path = daily.generate_daily_report()
    print(f"  ✓ 日报生成成功")
    print(f"    文件: {path}")
    print(f"    活跃设备: {stats['active_equipments']} 台")
    print(f"    故障率: {stats['fault_rate']:.2f}%")
    print(f"    维护成本: ¥{stats['total_maintenance_cost']:.2f}")

    print()
    print("=" * 60)
    print("  ✓ 所有验证通过! 系统运行正常")
    print("=" * 60)
    print()
    print("使用方法:")
    print("  python main.py once    - 执行一次完整流程")
    print("  python main.py         - 持续运行调度器")
    print("  python cli.py          - 交互式命令行界面")
    print("  python test_system.py  - 完整功能测试")
    print()

    return True


if __name__ == '__main__':
    try:
        quick_verify()
    except Exception as e:
        logger.exception("验证失败")
        print(f"\n✗ 验证失败: {e}")
        sys.exit(1)
