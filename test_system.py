#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import PredictiveMaintenanceSystem
from core.logger import logger
from utils.helpers import now_str, today_str


def run_tests():
    print("=" * 60)
    print("  制造业生产设备预测性维护与备件智能管理系统 - 测试")
    print("=" * 60)
    print()

    print("[1/10] 初始化系统...")
    system = PredictiveMaintenanceSystem()
    system.initialize(seed_data=True)
    modules = system.get_status()
    print("  ✓ 系统初始化完成")

    print("\n[2/10] 测试传感器数据采集...")
    collector = modules['sensor_collector']
    count = collector.collect_all()
    assert count > 0, f"数据采集失败: {count}"
    print(f"  ✓ 采集了 {count} 条传感器数据")

    print("\n[3/10] 测试设备健康评估...")
    analyzer = modules['health_analyzer']
    results, high_risk = analyzer.analyze_all_equipments()
    assert len(results) > 0, "健康评估失败"
    print(f"  ✓ 评估了 {len(results)} 台设备, {len(high_risk)} 台高风险")

    if high_risk:
        print("\n[4/10] 测试预防性维护工单创建...")
        wo_mgr = modules['work_order_manager']
        created = wo_mgr.create_orders_for_high_risk(high_risk)
        print(f"  ✓ 创建了 {created} 个预防性维护工单")

        print("\n[5/10] 测试工单状态流转...")
        orders = wo_mgr.list_orders(limit=5)
        if orders:
            order = orders[0]
            success = wo_mgr.update_status(order['id'], 'in_progress', 'tester', '测试流转')
            assert success, "工单状态更新失败"
            success = wo_mgr.update_status(order['id'], 'completed', 'tester', '测试完成')
            assert success, "工单状态更新失败"
            print(f"  ✓ 工单 {order['order_no']} 状态流转成功")
    else:
        print("\n[4-5/10] 暂无高风险设备, 跳过工单测试")

    print("\n[6/10] 测试维护效果验证...")
    verifier = system.scheduler.verifier
    verified = verifier.batch_verify_completed_orders()
    print(f"  ✓ 验证了 {verified} 个工单")

    print("\n[7/10] 测试库存管理...")
    inv_mgr = modules['inventory_manager']
    inv_mgr.update_all_safety_stocks()
    low_stock = inv_mgr.check_low_stock()
    print(f"  ✓ 检查了 {len(low_stock)} 个低库存备件")

    print("\n[8/10] 测试供应商与采购...")
    sup_mgr = modules['supplier_manager']
    suppliers = sup_mgr.list_suppliers()
    assert len(suppliers) > 0, "供应商数据缺失"

    requisitions = inv_mgr.list_requisitions(status='pending')
    approved_count = 0
    for req in requisitions[:3]:
        if inv_mgr.approve_requisition(req['id'], 'test_approver', True):
            approved_count += 1
    if approved_count > 0:
        created_orders = sup_mgr.process_approved_requisitions()
        print(f"  ✓ 审批了 {approved_count} 个申请, 创建了 {created_orders} 个采购订单")
    else:
        print(f"  ✓ 供应商: {len(suppliers)} 个, 暂无待审批申请")

    print("\n[9/10] 测试报告生成...")
    daily_report = modules['daily_report']
    stats, daily_path = daily_report.generate_daily_report()
    assert os.path.exists(daily_path), f"日报文件未生成: {daily_path}"
    print(f"  ✓ 日报已生成: {daily_path}")

    monthly_report = modules['monthly_report']
    m_stats, pdf_path, excel_path = monthly_report.generate_monthly_report()
    print(f"  ✓ 月度报告已生成:")
    print(f"    - PDF: {pdf_path}")
    print(f"    - Excel: {excel_path}")
    print(f"    - 生命周期总成本: ¥{m_stats['total_lifecycle_cost']:,.2f}")

    print("\n[10/10] 测试日志查询与导出...")
    log_query = modules['log_query']
    logs = log_query.query_logs(limit=10)
    assert len(logs) > 0, "操作日志为空"

    export_path = log_query.batch_export('logs', None)
    assert export_path and os.path.exists(export_path), "日志导出失败"
    print(f"  ✓ 查询到 {len(logs)} 条日志, 已导出到: {export_path}")

    print("\n" + "=" * 60)
    print("  ✓ 所有测试通过!")
    print("=" * 60)
    print()
    print("系统功能测试摘要:")
    print(f"  数据采集: {count} 条/轮")
    print(f"  设备评估: {len(results)} 台")
    print(f"  高风险设备: {len(high_risk)} 台")
    print(f"  低库存备件: {len(low_stock)} 个")
    print(f"  日报故障率: {stats['fault_rate']:.2f}%")
    print(f"  月度生命周期成本: ¥{m_stats['total_lifecycle_cost']:,.2f}")
    print()
    print("运行交互式界面: python cli.py")
    print("运行一次完整流程: python main.py once")
    print("持续运行调度器: python main.py")
    print()

    return True


if __name__ == '__main__':
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("测试异常")
        print(f"\n✗ 测试异常: {e}")
        sys.exit(1)
