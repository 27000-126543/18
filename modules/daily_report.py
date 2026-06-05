import os
from datetime import datetime, timedelta
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import today_str, now_str, safe_float, safe_int, op_logger
from config.settings import REPORT_CONFIG
from modules.notifications import NotificationManager


class DailyReportGenerator:
    def __init__(self):
        self.output_dir = REPORT_CONFIG['report_output_dir']
        os.makedirs(self.output_dir, exist_ok=True)

    def _collect_daily_stats(self, report_date=None):
        if not report_date:
            report_date = today_str()

        stats = {
            'report_date': report_date,
            'total_equipments': 0,
            'active_equipments': 0,
            'fault_count': 0,
            'fault_rate': 0.0,
            'avg_repair_time_hours': 0.0,
            'total_maintenance_cost': 0.0,
            'high_risk_equipments': 0,
            'pending_work_orders': 0,
            'completed_work_orders': 0,
            'low_stock_items': 0,
        }

        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM equipments")
            stats['total_equipments'] = safe_int(cursor.fetchone()['cnt'])

            cursor.execute("SELECT COUNT(*) as cnt FROM equipments WHERE status = 'active'")
            stats['active_equipments'] = safe_int(cursor.fetchone()['cnt'])

            cursor.execute(f"""
                SELECT COUNT(*) as cnt FROM sensor_data
                WHERE is_anomaly = 1
                AND date(collection_time) = ?
            """, (report_date,))
            stats['fault_count'] = safe_int(cursor.fetchone()['cnt'])

            if stats['active_equipments'] > 0:
                stats['fault_rate'] = round(stats['fault_count'] / stats['active_equipments'] * 100, 2)

            cursor.execute(f"""
                SELECT 
                    AVG((julianday(COALESCE(completed_at, updated_at)) - julianday(created_at)) * 24) as avg_hours,
                    COALESCE(SUM(maintenance_cost), 0) as total_cost,
                    SUM(CASE WHEN status IN ('pending', 'in_progress') THEN 1 ELSE 0 END) as pending_cnt,
                    SUM(CASE WHEN status IN ('completed', 'verified') THEN 1 ELSE 0 END) as completed_cnt
                FROM work_orders
                WHERE date(created_at) = ?
            """, (report_date,))
            row = cursor.fetchone()
            stats['avg_repair_time_hours'] = round(safe_float(row['avg_hours']), 2)
            stats['total_maintenance_cost'] = round(safe_float(row['total_cost']), 2)
            stats['pending_work_orders'] = safe_int(row['pending_cnt'])
            stats['completed_work_orders'] = safe_int(row['completed_cnt'])

            cursor.execute("""
                SELECT COUNT(*) as cnt FROM spare_parts WHERE current_stock <= safety_stock
            """)
            stats['low_stock_items'] = safe_int(cursor.fetchone()['cnt'])

            cursor.execute(f"""
                SELECT COUNT(DISTINCT equipment_id) as cnt FROM equipment_health_records
                WHERE health_status IN ('high_risk', 'medium_risk')
                AND record_date = ?
            """, (report_date,))
            stats['high_risk_equipments'] = safe_int(cursor.fetchone()['cnt'])

        return stats

    def _generate_text_report(self, stats):
        lines = []
        lines.append("=" * 60)
        lines.append(f"  制造业设备预测性维护与备件管理日报")
        lines.append(f"  报告日期: {stats['report_date']}")
        lines.append("=" * 60)
        lines.append("")
        lines.append("【设备概况】")
        lines.append(f"  设备总数: {stats['total_equipments']} 台")
        lines.append(f"  活跃设备: {stats['active_equipments']} 台")
        lines.append(f"  高风险设备: {stats['high_risk_equipments']} 台")
        lines.append("")
        lines.append("【故障统计】")
        lines.append(f"  今日异常数据点: {stats['fault_count']} 个")
        lines.append(f"  设备故障率: {stats['fault_rate']:.2f}%")
        lines.append(f"  平均修复时间: {stats['avg_repair_time_hours']:.2f} 小时")
        lines.append("")
        lines.append("【工单状态】")
        lines.append(f"  待处理工单: {stats['pending_work_orders']} 个")
        lines.append(f"  已完成工单: {stats['completed_work_orders']} 个")
        lines.append(f"  今日维护成本: ¥{stats['total_maintenance_cost']:.2f}")
        lines.append("")
        lines.append("【库存状态】")
        lines.append(f"  低库存备件: {stats['low_stock_items']} 个")
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"  生成时间: {now_str()}")
        lines.append("=" * 60)
        return '\n'.join(lines)

    def generate_daily_report(self, report_date=None):
        if not report_date:
            report_date = today_str()

        logger.info(f"开始生成 {report_date} 日报...")

        stats = self._collect_daily_stats(report_date)
        report_content = self._generate_text_report(stats)

        report_file = os.path.join(self.output_dir, f'daily_report_{report_date}.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_reports
                    (report_date, total_equipments, active_equipments, fault_count, fault_rate,
                     avg_repair_time_hours, total_maintenance_cost, high_risk_equipments,
                     pending_work_orders, completed_work_orders, low_stock_items, report_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_date, stats['total_equipments'], stats['active_equipments'],
                    stats['fault_count'], stats['fault_rate'], stats['avg_repair_time_hours'],
                    stats['total_maintenance_cost'], stats['high_risk_equipments'],
                    stats['pending_work_orders'], stats['completed_work_orders'],
                    stats['low_stock_items'], report_file
                ))
        except Exception as e:
            logger.error(f"保存日报记录失败: {e}")

        NotificationManager.notify_daily_report_ready(report_date, report_file)

        op_logger.log(
            'generate_daily_report', 'report',
            f'生成 {report_date} 日报, 故障率 {stats["fault_rate"]:.2f}%, 维护成本 ¥{stats["total_maintenance_cost"]:.2f}'
        )

        logger.info(f"日报已生成: {report_file}")
        return stats, report_file

    def get_recent_reports(self, days=7):
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM daily_reports
                WHERE report_date >= date('now', '-{days} days')
                ORDER BY report_date DESC
            """)
            return [dict(r) for r in cursor.fetchall()]
