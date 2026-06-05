#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import PredictiveMaintenanceSystem
from utils.helpers import now_str, today_str, month_str
from core.logger import logger


class InteractiveCLI:
    def __init__(self, system):
        self.system = system
        self.modules = system.get_status()

    def show_menu(self):
        print("\n" + "=" * 60)
        print("  制造业生产设备预测性维护与备件智能管理系统")
        print("=" * 60)
        print()
        print("【数据采集与健康评估】")
        print("  1. 执行一次传感器数据采集")
        print("  2. 执行设备健康评估")
        print("  3. 查看高风险设备列表")
        print()
        print("【工单管理】")
        print("  4. 查看工单列表")
        print("  5. 更新工单状态")
        print("  6. 检查并升级超时工单")
        print("  7. 批量验证已完成工单")
        print()
        print("【备件与采购】")
        print("  8. 查看备件库存")
        print("  9. 检查低库存并生成采购申请")
        print("  10. 查看采购申请")
        print("  11. 审批采购申请")
        print("  12. 处理已审批采购申请（生成订单）")
        print("  13. 查看供应商列表")
        print("  14. 查看采购订单")
        print()
        print("【设备管理】")
        print("  15. 查看设备列表")
        print("  16. 报废设备")
        print("  17. 查看设备健康历史")
        print()
        print("【报告与导出】")
        print("  18. 生成今日日报")
        print("  19. 查看历史日报")
        print("  20. 生成月度报告")
        print("  21. 查看月度报告")
        print()
        print("【日志查询】")
        print("  22. 查询操作日志")
        print("  23. 查询工单历史记录")
        print("  24. 查询传感器数据")
        print("  25. 批量导出数据")
        print()
        print("【系统】")
        print("  26. 执行一次完整流程")
        print("  0. 退出")
        print()

    def run(self):
        while True:
            try:
                self.show_menu()
                choice = input("请选择操作 [0-26]: ").strip()

                if choice == '0':
                    print("感谢使用，再见！")
                    break
                elif choice == '1':
                    self.action_collect_sensor_data()
                elif choice == '2':
                    self.action_health_analysis()
                elif choice == '3':
                    self.action_show_high_risk()
                elif choice == '4':
                    self.action_list_work_orders()
                elif choice == '5':
                    self.action_update_work_order()
                elif choice == '6':
                    self.action_check_timeouts()
                elif choice == '7':
                    self.action_verify_orders()
                elif choice == '8':
                    self.action_list_parts()
                elif choice == '9':
                    self.action_check_inventory()
                elif choice == '10':
                    self.action_list_requisitions()
                elif choice == '11':
                    self.action_approve_requisition()
                elif choice == '12':
                    self.action_process_purchases()
                elif choice == '13':
                    self.action_list_suppliers()
                elif choice == '14':
                    self.action_list_purchase_orders()
                elif choice == '15':
                    self.action_list_equipments()
                elif choice == '16':
                    self.action_scrap_equipment()
                elif choice == '17':
                    self.action_health_history()
                elif choice == '18':
                    self.action_generate_daily_report()
                elif choice == '19':
                    self.action_show_daily_reports()
                elif choice == '20':
                    self.action_generate_monthly_report()
                elif choice == '21':
                    self.action_show_monthly_reports()
                elif choice == '22':
                    self.action_query_logs()
                elif choice == '23':
                    self.action_query_work_orders()
                elif choice == '24':
                    self.action_query_sensor_data()
                elif choice == '25':
                    self.action_batch_export()
                elif choice == '26':
                    self.action_run_full_flow()
                else:
                    print("无效的选择，请重新输入！")

            except KeyboardInterrupt:
                print("\n\n返回菜单...")
            except Exception as e:
                logger.error(f"操作异常: {e}")
                print(f"操作失败: {e}")

            input("\n按回车键继续...")

    def action_collect_sensor_data(self):
        print("\n开始采集传感器数据...")
        count = self.modules['sensor_collector'].collect_all()
        print(f"采集完成: {count} 条数据")

    def action_health_analysis(self):
        print("\n开始设备健康评估...")
        results, high_risk = self.modules['health_analyzer'].analyze_all_equipments()
        print(f"评估完成: {len(results)} 台设备")
        print(f"高风险设备: {len(high_risk)} 台")
        if high_risk:
            created = self.modules['work_order_manager'].create_orders_for_high_risk(high_risk)
            print(f"生成预防性维护工单: {created} 个")

    def action_show_high_risk(self):
        print("\n高风险设备列表:")
        equipments = self.modules['health_analyzer'].get_risk_equipments('medium_risk')
        if not equipments:
            print("  暂无高风险设备")
            return
        print(f"  {'设备编号':<12} {'设备名称':<20} {'位置':<8} {'评分':>6} {'状态':<12}")
        print("  " + "-" * 60)
        for eq in equipments[:20]:
            print(f"  {eq['equipment_code']:<12} {eq['name'][:20]:<20} {eq['location']:<8} "
                  f"{eq['rul_score']:>6.1f} {eq['health_status']:<12}")

    def action_list_work_orders(self):
        status = input("请输入工单状态筛选 (pending/in_progress/completed/verified, 回车全部): ").strip() or None
        orders = self.modules['work_order_manager'].list_orders(status=status, limit=50)
        print(f"\n工单列表 (共 {len(orders)} 个):")
        if not orders:
            print("  暂无工单")
            return
        print(f"  {'工单号':<18} {'设备':<12} {'优先级':<8} {'状态':<12} {'工程师':<10}")
        print("  " + "-" * 60)
        for wo in orders:
            print(f"  {wo['order_no']:<18} {wo['equipment_code']:<12} {wo['priority']:<8} "
                  f"{wo['status']:<12} {(wo.get('engineer_name') or '-'):<10}")

    def action_update_work_order(self):
        order_id = input("请输入工单ID: ").strip()
        if not order_id:
            return
        new_status = input("请输入新状态 (pending/in_progress/completed/verified): ").strip()
        operator = input("操作人 (默认system): ").strip() or 'system'
        note = input("备注 (可选): ").strip()

        result = self.modules['work_order_manager'].update_status(int(order_id), new_status, operator, note)
        print(f"状态更新: {'成功' if result else '失败'}")

    def action_check_timeouts(self):
        print("\n检查超时工单...")
        count = self.modules['work_order_manager'].check_timeouts_and_escalate()
        print(f"升级了 {count} 个超时工单")

    def action_verify_orders(self):
        print("\n批量验证已完成工单...")
        count = self.system.scheduler.verifier.batch_verify_completed_orders()
        print(f"验证了 {count} 个工单")

    def action_list_parts(self):
        low_only = input("只显示低库存? (y/n, 默认n): ").strip().lower() == 'y'
        parts = self.modules['inventory_manager'].list_parts(low_stock_only=low_only)
        print(f"\n备件列表 (共 {len(parts)} 个):")
        if not parts:
            print("  暂无备件")
            return
        print(f"  {'编码':<10} {'名称':<18} {'单价':>10} {'当前库存':>10} {'安全库存':>10}")
        print("  " + "-" * 60)
        for p in parts[:30]:
            print(f"  {p['part_code']:<10} {p['name'][:18]:<18} ¥{p['unit_price']:>8.2f} "
                  f"{p['current_stock']:>10} {p['safety_stock']:>10}")

    def action_check_inventory(self):
        print("\n检查库存...")
        self.modules['inventory_manager'].update_all_safety_stocks()
        low_stock = self.modules['inventory_manager'].check_low_stock()
        print(f"低库存/缺货备件: {len(low_stock)} 个")

    def action_list_requisitions(self):
        status = input("状态筛选 (pending/approved/needs_approval, 回车全部): ").strip() or None
        reqs = self.modules['inventory_manager'].list_requisitions(status=status)
        print(f"\n采购申请列表 (共 {len(reqs)} 个):")
        if not reqs:
            print("  暂无采购申请")
            return
        print(f"  {'申请号':<18} {'备件':<15} {'数量':>6} {'预估金额':>12} {'审批状态':<16}")
        print("  " + "-" * 70)
        for r in reqs:
            print(f"  {r['req_no']:<18} {r['part_name'][:15]:<15} {r['quantity']:>6} "
                  f"¥{r['estimated_cost']:>10.2f} {r['approval_status']:<16}")

    def action_approve_requisition(self):
        req_id = input("请输入采购申请ID: ").strip()
        if not req_id:
            return
        approve = input("通过审批? (y/n, 默认y): ").strip().lower() != 'n'
        approver = input("审批人 (默认admin): ").strip() or 'admin'

        result = self.modules['inventory_manager'].approve_requisition(int(req_id), approver, approve)
        print(f"审批: {'成功' if result else '失败'}")

    def action_process_purchases(self):
        print("\n处理已审批采购申请...")
        count = self.modules['supplier_manager'].process_approved_requisitions()
        print(f"创建了 {count} 个采购订单")

    def action_list_suppliers(self):
        suppliers = self.modules['supplier_manager'].list_suppliers()
        print(f"\n供应商列表 (共 {len(suppliers)} 个):")
        if not suppliers:
            print("  暂无供应商")
            return
        print(f"  {'编码':<10} {'名称':<25} {'质量':>6} {'交付':>6} {'价格':>6} {'综合':>6}")
        print("  " + "-" * 60)
        for s in suppliers:
            print(f"  {s['supplier_code']:<10} {s['name'][:25]:<25} "
                  f"{s['quality_score']:>6.1f} {s['delivery_score']:>6.1f} "
                  f"{s['price_score']:>6.1f} {s['overall_score']:>6.1f}")

    def action_list_purchase_orders(self):
        status = input("状态筛选 (pending/shipped/received, 回车全部): ").strip() or None
        pos = self.modules['supplier_manager'].list_purchase_orders(status=status)
        print(f"\n采购订单列表 (共 {len(pos)} 个):")
        if not pos:
            print("  暂无采购订单")
            return
        print(f"  {'订单号':<18} {'备件':<12} {'供应商':<15} {'数量':>6} {'金额':>12} {'状态':<10}")
        print("  " + "-" * 75)
        for po in pos:
            print(f"  {po['order_no']:<18} {po['part_name'][:12]:<12} {po['supplier_name'][:15]:<15} "
                  f"{po['quantity']:>6} ¥{po['total_amount']:>10.2f} {po['status']:<10}")

    def action_list_equipments(self):
        eqs = self.modules['equipment_scrap'].get_active_equipments()
        print(f"\n活跃设备列表 (共 {len(eqs)} 台):")
        if not eqs:
            print("  暂无设备")
            return
        print(f"  {'编号':<12} {'名称':<20} {'类型':<15} {'位置':<8} {'状态':<10}")
        print("  " + "-" * 65)
        for eq in eqs[:30]:
            print(f"  {eq['equipment_code']:<12} {eq['name'][:20]:<20} "
                  f"{eq['type'][:15]:<15} {eq['location']:<8} {eq['status']:<10}")

    def action_scrap_equipment(self):
        eq_code = input("请输入设备编号: ").strip()
        if not eq_code:
            return
        eq = self.modules['equipment_scrap'].get_equipment(equipment_code=eq_code)
        if not eq:
            print(f"设备 {eq_code} 不存在")
            return

        reason = input("报废原因: ").strip()
        if not reason:
            print("请输入报废原因")
            return
        residual = float(input("残值 (默认0): ").strip() or 0)
        operator = input("操作人 (默认system): ").strip() or 'system'

        result = self.modules['equipment_scrap'].scrap_equipment(eq['id'], reason, residual, operator)
        if result:
            print(f"设备 {eq_code} 已报废")
            if result.get('related_parts'):
                print(f"关联备件: {len(result['related_parts'])} 个")
        else:
            print("报废失败")

    def action_health_history(self):
        eq_code = input("请输入设备编号: ").strip()
        if not eq_code:
            return
        eq = self.modules['equipment_scrap'].get_equipment(equipment_code=eq_code)
        if not eq:
            print(f"设备 {eq_code} 不存在")
            return

        history = self.modules['health_analyzer'].get_equipment_health_history(eq['id'], days=30)
        print(f"\n设备 {eq_code} 健康历史 (近30天):")
        if not history:
            print("  暂无记录")
            return
        print(f"  {'日期':<12} {'评分':>6} {'状态':<12} {'温度':>8} {'振动':>8} {'异常数':>6}")
        print("  " + "-" * 55)
        for h in history:
            print(f"  {h['record_date']:<12} {h['rul_score']:>6.1f} {h['health_status']:<12} "
                  f"{(h.get('temperature_avg') or 0):>8.1f} {(h.get('vibration_avg') or 0):>8.3f} "
                  f"{h.get('anomalies_detected', 0):>6}")

    def action_generate_daily_report(self):
        print("\n生成日报...")
        stats, path = self.modules['daily_report'].generate_daily_report()
        print(f"日报已生成: {path}")
        print(f"  故障率: {stats['fault_rate']:.2f}%")
        print(f"  高风险设备: {stats['high_risk_equipments']} 台")
        print(f"  维护成本: ¥{stats['total_maintenance_cost']:.2f}")

    def action_show_daily_reports(self):
        reports = self.modules['daily_report'].get_recent_reports(days=14)
        print(f"\n历史日报 (近14天):")
        if not reports:
            print("  暂无报告")
            return
        print(f"  {'日期':<12} {'故障数':>8} {'故障率':>8} {'MTTR(h)':>8} {'成本':>12} {'高风险':>8}")
        print("  " + "-" * 60)
        for r in reports:
            print(f"  {r['report_date']:<12} {r['fault_count']:>8} {r['fault_rate']:>7.2f}% "
                  f"{r['avg_repair_time_hours']:>8.2f} ¥{r['total_maintenance_cost']:>10.2f} "
                  f"{r['high_risk_equipments']:>8}")

    def action_generate_monthly_report(self):
        print("\n生成月度报告...")
        stats, pdf, excel = self.modules['monthly_report'].generate_monthly_report()
        print(f"月度报告已生成:")
        print(f"  PDF: {pdf}")
        print(f"  Excel: {excel}")
        print(f"  生命周期总成本: ¥{stats['total_lifecycle_cost']:,.2f}")

    def action_show_monthly_reports(self):
        reports = self.modules['monthly_report'].get_reports()
        print(f"\n月度报告历史:")
        if not reports:
            print("  暂无报告")
            return
        print(f"  {'周期':<10} {'设备原值':>14} {'维护成本':>14} {'备件成本':>14} {'总成本':>14}")
        print("  " + "-" * 66)
        for r in reports:
            print(f"  {r['report_month']:<10} ¥{r['total_equipment_cost']:>12,.2f} "
                  f"¥{r['total_maintenance_cost']:>12,.2f} ¥{r['total_parts_cost']:>12,.2f} "
                  f"¥{r['total_lifecycle_cost']:>12,.2f}")

    def action_query_logs(self):
        eq_code = input("设备编号 (回车全部): ").strip() or None
        op_type = input("操作类型 (回车全部): ").strip() or None
        module = input("模块 (回车全部): ").strip() or None

        logs = self.modules['log_query'].query_logs(
            equipment_code=eq_code, operation_type=op_type, module=module, limit=50
        )
        print(f"\n操作日志 (共 {len(logs)} 条):")
        if not logs:
            print("  暂无日志")
            return
        print(f"  {'时间':<20} {'模块':<18} {'操作类型':<18} {'描述'}")
        print("  " + "-" * 80)
        for l in logs[:30]:
            print(f"  {l['created_at']:<20} {l['module'][:18]:<18} "
                  f"{l['operation_type'][:18]:<18} {l['description'][:50]}")

    def action_query_work_orders(self):
        eq_code = input("设备编号 (回车全部): ").strip() or None
        status = input("状态 (回车全部): ").strip() or None
        orders = self.modules['log_query'].query_work_order_history(
            equipment_code=eq_code, status=status, limit=50
        )
        print(f"\n工单历史 (共 {len(orders)} 条):")
        if not orders:
            print("  暂无记录")
            return
        print(f"  {'工单号':<18} {'设备':<12} {'优先级':<8} {'状态':<12} {'创建时间':<20}")
        print("  " + "-" * 70)
        for wo in orders:
            print(f"  {wo['order_no']:<18} {wo['equipment_code']:<12} "
                  f"{wo['priority']:<8} {wo['status']:<12} {wo['created_at']:<20}")

    def action_query_sensor_data(self):
        eq_code = input("设备编号: ").strip()
        if not eq_code:
            return
        anomaly_only = input("只看异常数据? (y/n, 默认n): ").strip().lower() == 'y'

        data = self.modules['log_query'].query_sensor_data(
            equipment_code=eq_code,
            is_anomaly=True if anomaly_only else None,
            limit=50
        )
        print(f"\n传感器数据 (共 {len(data)} 条):")
        if not data:
            print("  暂无数据")
            return
        print(f"  {'采集时间':<20} {'温度':>8} {'振动':>8} {'电流':>8} {'异常':>6}")
        print("  " + "-" * 55)
        for d in data:
            print(f"  {d['collection_time']:<20} {d.get('temperature', 0):>8.2f} "
                  f"{d.get('vibration', 0):>8.4f} {d.get('current', 0):>8.2f} "
                  f"{'是' if d.get('is_anomaly') else '否':>6}")

    def action_batch_export(self):
        print("\n导出类型:")
        print("  1. 操作日志")
        print("  2. 工单历史")
        print("  3. 传感器数据")
        choice = input("请选择 [1-3]: ").strip()

        type_map = {'1': 'logs', '2': 'work_orders', '3': 'sensor_data'}
        export_type = type_map.get(choice)
        if not export_type:
            print("无效选择")
            return

        filepath = self.modules['log_query'].batch_export(export_type, None)
        if filepath:
            print(f"数据已导出到: {filepath}")
        else:
            print("导出失败")

    def action_run_full_flow(self):
        print("\n执行完整系统流程...")
        self.system.scheduler.run_all_once()


def main():
    print("正在初始化系统...")
    system = PredictiveMaintenanceSystem()
    system.initialize(seed_data=True)

    cli = InteractiveCLI(system)
    cli.run()


if __name__ == '__main__':
    main()
