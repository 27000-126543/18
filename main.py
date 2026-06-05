import time
import threading
from datetime import datetime
from core.logger import logger
from models.schema import init_database
from modules.sensor_collector import SensorDataCollector
from modules.health_analyzer import HealthAnalyzer
from modules.work_order_manager import WorkOrderManager
from modules.maintenance_verifier import MaintenanceVerifier
from modules.inventory_manager import InventoryManager
from modules.supplier_manager import SupplierManager
from modules.daily_report import DailyReportGenerator
from modules.monthly_report import MonthlyReportGenerator
from modules.equipment_scrap import EquipmentScrapManager
from modules.log_query import LogQueryManager
from modules.data_initializer import DataInitializer
from config.settings import SCHEDULER_CONFIG


class TaskScheduler:
    def __init__(self):
        self.sensor_collector = SensorDataCollector()
        self.health_analyzer = HealthAnalyzer()
        self.work_order_mgr = WorkOrderManager()
        self.verifier = MaintenanceVerifier()
        self.inventory_mgr = InventoryManager()
        self.supplier_mgr = SupplierManager()
        self.daily_report = DailyReportGenerator()
        self.monthly_report = MonthlyReportGenerator()
        self.scrap_mgr = EquipmentScrapManager()
        self.log_query = LogQueryManager()

        self._running = False
        self._tasks = {}

    def task_collect_sensor_data(self):
        try:
            logger.info("=== 执行: 传感器数据采集 ===")
            count = self.sensor_collector.collect_all()
            logger.info(f"数据采集完成: {count} 条")
        except Exception as e:
            logger.error(f"数据采集任务失败: {e}")

    def task_health_analysis(self):
        try:
            logger.info("=== 执行: 设备健康评估 ===")
            results, high_risk = self.health_analyzer.analyze_all_equipments()
            logger.info(f"健康评估完成: {len(results)} 台, {len(high_risk)} 台需关注")

            if high_risk:
                created = self.work_order_mgr.create_orders_for_high_risk(high_risk)
                logger.info(f"生成预防性维护工单: {created} 个")
        except Exception as e:
            logger.error(f"健康评估任务失败: {e}")

    def task_check_work_orders(self):
        try:
            logger.info("=== 执行: 工单超时检查 ===")
            escalated = self.work_order_mgr.check_timeouts_and_escalate()
            logger.info(f"超时检查完成: {escalated} 个工单升级")
        except Exception as e:
            logger.error(f"工单检查任务失败: {e}")

    def task_check_inventory(self):
        try:
            logger.info("=== 执行: 库存检查 ===")
            self.inventory_mgr.update_all_safety_stocks()
            low_stock = self.inventory_mgr.check_low_stock()
            logger.info(f"库存检查完成: {len(low_stock)} 个低库存")
        except Exception as e:
            logger.error(f"库存检查任务失败: {e}")

    def task_process_purchases(self):
        try:
            logger.info("=== 执行: 采购订单处理 ===")
            count = self.supplier_mgr.process_approved_requisitions()
            logger.info(f"采购处理完成: {count} 个订单")
        except Exception as e:
            logger.error(f"采购处理任务失败: {e}")

    def task_verify_maintenance(self):
        try:
            logger.info("=== 执行: 维护效果验证 ===")
            verified = self.verifier.batch_verify_completed_orders()
            logger.info(f"维护验证完成: {verified} 个工单")
        except Exception as e:
            logger.error(f"维护验证任务失败: {e}")

    def task_daily_report(self):
        try:
            logger.info("=== 执行: 生成日报 ===")
            stats, path = self.daily_report.generate_daily_report()
            logger.info(f"日报已生成: {path}")
        except Exception as e:
            logger.error(f"日报生成任务失败: {e}")

    def task_monthly_report(self):
        try:
            if datetime.now().day == 1:
                logger.info("=== 执行: 生成月度报告 ===")
                stats, pdf, excel = self.monthly_report.generate_monthly_report()
                logger.info(f"月度报告已生成: PDF={pdf}, Excel={excel}")
        except Exception as e:
            logger.error(f"月度报告生成任务失败: {e}")

    def run_all_once(self):
        logger.info("=" * 60)
        logger.info("执行一次完整的系统流程...")
        logger.info("=" * 60)

        self.task_collect_sensor_data()
        self.task_health_analysis()
        self.task_check_work_orders()
        self.task_verify_maintenance()
        self.task_check_inventory()
        self.task_process_purchases()

        logger.info("=" * 60)
        logger.info("系统流程执行完成!")
        logger.info("=" * 60)

    def start_scheduler(self):
        self._running = True
        logger.info("调度器已启动...")

        threads = []

        def run_with_interval(task_func, interval_seconds, name):
            while self._running:
                try:
                    logger.info(f"[{name}] 开始执行...")
                    task_func()
                except Exception as e:
                    logger.error(f"[{name}] 执行异常: {e}")
                for _ in range(interval_seconds):
                    if not self._running:
                        break
                    time.sleep(1)

        tasks = [
            (self.task_collect_sensor_data, 60, "数据采集"),
            (self.task_health_analysis, 1800, "健康评估"),
            (self.task_check_work_orders, 900, "工单检查"),
            (self.task_check_inventory, 21600, "库存检查"),
            (self.task_process_purchases, 10800, "采购处理"),
            (self.task_verify_maintenance, 3600, "维护验证"),
        ]

        for task_func, interval, name in tasks:
            t = threading.Thread(target=run_with_interval, args=(task_func, interval, name), daemon=True)
            threads.append(t)
            t.start()

        return threads

    def stop_scheduler(self):
        self._running = False
        logger.info("调度器正在停止...")


class PredictiveMaintenanceSystem:
    def __init__(self):
        self.scheduler = TaskScheduler()

    def initialize(self, seed_data=True):
        logger.info("正在初始化系统...")
        init_database()
        logger.info("数据库初始化完成")

        if seed_data:
            initializer = DataInitializer()
            initializer.seed_sample_data()

        logger.info("系统初始化完成!")
        return self

    def start(self, run_once=False):
        if run_once:
            self.scheduler.run_all_once()
            self.scheduler.task_daily_report()
            return

        threads = self.scheduler.start_scheduler()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n收到停止信号, 正在关闭系统...")
            self.scheduler.stop_scheduler()
            for t in threads:
                t.join(timeout=5)
            logger.info("系统已安全关闭")

    def get_status(self):
        return {
            'sensor_collector': self.scheduler.sensor_collector,
            'health_analyzer': self.scheduler.health_analyzer,
            'work_order_manager': self.scheduler.work_order_mgr,
            'inventory_manager': self.scheduler.inventory_mgr,
            'supplier_manager': self.scheduler.supplier_mgr,
            'daily_report': self.scheduler.daily_report,
            'monthly_report': self.scheduler.monthly_report,
            'equipment_scrap': self.scheduler.scrap_mgr,
            'log_query': self.scheduler.log_query,
        }


def main():
    import sys

    system = PredictiveMaintenanceSystem()
    system.initialize(seed_data=True)

    if len(sys.argv) > 1 and sys.argv[1] == 'once':
        system.start(run_once=True)
    else:
        print("=" * 60)
        print("  制造业生产设备预测性维护与备件智能管理系统")
        print("=" * 60)
        print()
        print("运行模式:")
        print("  1. 执行一次完整流程 (python main.py once)")
        print("  2. 持续运行调度器 (python main.py)")
        print()
        print("当前模式: 持续运行调度器")
        print("按 Ctrl+C 停止系统")
        print()
        system.start(run_once=False)


if __name__ == '__main__':
    main()
