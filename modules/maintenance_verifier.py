from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import now_str, today_str, safe_float, op_logger, parse_datetime
from modules.work_order_manager import WorkOrderManager


class MaintenanceVerifier:
    def __init__(self):
        self.work_order_mgr = WorkOrderManager()

    def _get_equipment_metrics_before(self, equipment_id, before_time, hours=24):
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    AVG(temperature) as temp_avg,
                    AVG(vibration) as vib_avg,
                    AVG(current) as curr_avg
                FROM sensor_data
                WHERE equipment_id = ? 
                AND collection_time < ?
                AND collection_time >= datetime(?, '-{hours} hours')
            """, (equipment_id, before_time, before_time))
            row = cursor.fetchone()
            return {
                'temp_avg': safe_float(row['temp_avg']),
                'vib_avg': safe_float(row['vib_avg']),
                'curr_avg': safe_float(row['curr_avg']),
            } if row else {}

    def _get_equipment_metrics_after(self, equipment_id, after_time, hours=24):
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    AVG(temperature) as temp_avg,
                    AVG(vibration) as vib_avg,
                    AVG(current) as curr_avg
                FROM sensor_data
                WHERE equipment_id = ? 
                AND collection_time > ?
                AND collection_time <= datetime(?, '+{hours} hours')
            """, (equipment_id, after_time, after_time))
            row = cursor.fetchone()
            return {
                'temp_avg': safe_float(row['temp_avg']),
                'vib_avg': safe_float(row['vib_avg']),
                'curr_avg': safe_float(row['curr_avg']),
            } if row else {}

    def _calculate_improvement_rate(self, pre_metrics, post_metrics):
        improvements = []
        for key in ['temp_avg', 'vib_avg', 'curr_avg']:
            pre = pre_metrics.get(key, 0)
            post = post_metrics.get(key, 0)
            if pre > 0 and post > 0:
                imp = (pre - post) / pre * 100
                improvements.append(imp)

        if not improvements:
            return 0.0
        return sum(improvements) / len(improvements)

    def verify_maintenance(self, work_order_id, verifier='system'):
        order = self.work_order_mgr.get_order(work_order_id)
        if not order:
            logger.error(f"工单 {work_order_id} 不存在")
            return None

        if order['status'] != 'completed':
            logger.warning(f"工单 {order['order_no']} 状态为 {order['status']}, 不能验证")
            return None

        completed_at = parse_datetime(order.get('completed_at') or order['updated_at'])
        if not completed_at:
            completed_at_str = now_str()
        else:
            completed_at_str = completed_at.strftime('%Y-%m-%d %H:%M:%S')

        pre_metrics = self._get_equipment_metrics_before(order['equipment_id'], completed_at_str)
        post_metrics = self._get_equipment_metrics_after(order['equipment_id'], completed_at_str)

        improvement_rate = self._calculate_improvement_rate(pre_metrics, post_metrics)
        is_passed = improvement_rate >= 10.0

        report_parts = []
        report_parts.append(f"维护效果验证报告 - 工单: {order['order_no']}")
        report_parts.append(f"设备: {order.get('equipment_code', 'N/A')} - {order.get('equipment_name', '')}")
        report_parts.append(f"")
        for key, label in [('temp_avg', '温度'), ('vib_avg', '振动'), ('curr_avg', '电流')]:
            pre = pre_metrics.get(key, 0)
            post = post_metrics.get(key, 0)
            if pre > 0:
                imp = (pre - post) / pre * 100
                report_parts.append(f"{label}: 维护前 {pre:.2f} -> 维护后 {post:.2f} (改善 {imp:.1f}%)")
        report_parts.append(f"")
        report_parts.append(f"综合改善率: {improvement_rate:.1f}%")
        report_parts.append(f"验证结果: {'通过' if is_passed else '未通过'}")
        report = '\n'.join(report_parts)

        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO maintenance_verifications
                    (work_order_id, equipment_id, pre_temperature_avg, post_temperature_avg,
                     pre_vibration_avg, post_vibration_avg, pre_current_avg, post_current_avg,
                     improvement_rate, is_passed, verifier, verification_date, report)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    work_order_id, order['equipment_id'],
                    pre_metrics.get('temp_avg'), post_metrics.get('temp_avg'),
                    pre_metrics.get('vib_avg'), post_metrics.get('vib_avg'),
                    pre_metrics.get('curr_avg'), post_metrics.get('curr_avg'),
                    improvement_rate, 1 if is_passed else 0,
                    verifier, today_str(), report
                ))

            if is_passed:
                self.work_order_mgr.update_status(
                    work_order_id, 'verified', verifier,
                    f'维护效果验证通过, 改善率: {improvement_rate:.1f}%'
                )

            op_logger.log(
                'verify_maintenance', 'maintenance_verification',
                f'验证工单 {order["order_no"]}: {"通过" if is_passed else "未通过"}, 改善率 {improvement_rate:.1f}%',
                equipment_code=order.get('equipment_code')
            )

            logger.info(f"工单 {order['order_no']} 验证: {'通过' if is_passed else '未通过'}, "
                         f"改善率 {improvement_rate:.1f}%")

            return {
                'work_order_id': work_order_id,
                'improvement_rate': improvement_rate,
                'is_passed': is_passed,
                'report': report,
                'pre_metrics': pre_metrics,
                'post_metrics': post_metrics,
            }

        except Exception as e:
            logger.error(f"验证维护效果失败: {e}")
            return None

    def batch_verify_completed_orders(self):
        orders = self.work_order_mgr.list_orders(status='completed')
        verified = 0
        for order in orders:
            result = self.verify_maintenance(order['id'])
            if result:
                verified += 1
        logger.info(f"批量验证完成: {verified}/{len(orders)} 个工单")
        return verified

    def get_verification_history(self, equipment_id=None, days=30):
        query = """
            SELECT mv.*, wo.order_no, e.equipment_code, e.name as equipment_name
            FROM maintenance_verifications mv
            JOIN work_orders wo ON mv.work_order_id = wo.id
            JOIN equipments e ON mv.equipment_id = e.id
            WHERE 1=1
        """
        params = []
        if equipment_id:
            query += " AND mv.equipment_id = ?"
            params.append(equipment_id)
        query += f" AND mv.verification_date >= date('now', '-{days} days')"
        query += " ORDER BY mv.verification_date DESC LIMIT 200"

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
