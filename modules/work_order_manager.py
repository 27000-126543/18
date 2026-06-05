from datetime import datetime, timedelta
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import (now_str, add_hours, generate_order_no,
                           safe_int, op_logger, parse_datetime)
from config.settings import WORK_ORDER_CONFIG
from modules.notifications import NotificationManager


class WorkOrderManager:
    def __init__(self):
        self.status_flow = WORK_ORDER_CONFIG['status_flow']
        self.timeout_hours = WORK_ORDER_CONFIG['timeout_escalation_hours']

    def get_deadline_hours(self, priority):
        if priority == 'high':
            return WORK_ORDER_CONFIG['high_risk_deadline_hours']
        elif priority == 'medium':
            return WORK_ORDER_CONFIG['medium_risk_deadline_hours']
        else:
            return WORK_ORDER_CONFIG['low_risk_deadline_hours']

    def _risk_to_priority(self, health_status):
        mapping = {
            'high_risk': 'high',
            'medium_risk': 'medium',
            'low_risk': 'low',
            'normal': 'low',
        }
        return mapping.get(health_status, 'low')

    def _find_best_engineer(self, equipment_type, equipment_location):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM engineers
                WHERE status = 'available'
                AND (specialty = ? OR specialty = 'general')
                AND location = ?
                ORDER BY workload ASC, rating DESC
                LIMIT 3
            """, (equipment_type, equipment_location))
            candidates = [dict(r) for r in cursor.fetchall()]

            if not candidates:
                cursor.execute("""
                    SELECT * FROM engineers
                    WHERE status = 'available'
                    ORDER BY workload ASC, rating DESC
                    LIMIT 3
                """)
                candidates = [dict(r) for r in cursor.fetchall()]

        return candidates[0] if candidates else None

    def create_preventive_order(self, equipment, rul_score, health_status, metrics=None):
        priority = self._risk_to_priority(health_status)
        deadline_hours = self.get_deadline_hours(priority)

        order_no = generate_order_no('WO')
        deadline = add_hours(deadline_hours)

        title = f"设备预防性维护 - {equipment.get('name', equipment.get('equipment_code', ''))}"
        description_parts = [
            f"设备健康评分: {rul_score:.1f}/100",
            f"风险等级: {health_status}",
        ]
        if metrics:
            if metrics.get('temp_avg'):
                description_parts.append(f"近期平均温度: {metrics['temp_avg']:.1f}°C")
            if metrics.get('vib_avg'):
                description_parts.append(f"近期平均振动: {metrics['vib_avg']:.3f}mm/s")
            if metrics.get('anomalies', 0) > 0:
                description_parts.append(f"异常数据点: {metrics['anomalies']} 个")
        description = '\n'.join(description_parts)

        engineer = self._find_best_engineer(equipment.get('type', ''), equipment.get('location', ''))

        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO work_orders
                    (order_no, equipment_id, title, description, priority, status,
                     engineer_id, assigned_at, deadline, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_no, equipment['id'], title, description, priority,
                    'in_progress' if engineer else 'pending',
                    engineer['id'] if engineer else None,
                    now_str() if engineer else None,
                    deadline, now_str(), now_str()
                ))
                order_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO work_order_status_history
                    (work_order_id, from_status, to_status, changed_by, note)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, None, 'in_progress' if engineer else 'pending',
                      'system', '系统自动生成预防性维护工单'))

                if engineer:
                    cursor.execute("""
                        UPDATE engineers SET workload = workload + 1 WHERE id = ?
                    """, (engineer['id'],))

            work_order = self.get_order(order_id)
            NotificationManager.notify_new_work_order(work_order, engineer)

            op_logger.log(
                'create_work_order', 'work_order',
                f'创建预防性维护工单 {order_no}, 优先级: {priority}, 设备: {equipment.get("equipment_code")}',
                equipment_code=equipment.get('equipment_code')
            )

            logger.info(f"创建预防性维护工单: {order_no}, 优先级: {priority}")
            return order_id, order_no

        except Exception as e:
            logger.error(f"创建预防性维护工单失败: {e}")
            return None, None

    def create_orders_for_high_risk(self, high_risk_list):
        created = 0
        for item in high_risk_list:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM work_orders
                    WHERE equipment_id = ? AND status IN ('pending', 'in_progress')
                """, (item['equipment_id'],))
                existing = cursor.fetchone()['cnt']

            if existing > 0:
                logger.info(f"设备 {item['equipment_code']} 已有未完成工单, 跳过")
                continue

            with get_db_cursor() as cursor:
                cursor.execute("SELECT * FROM equipments WHERE id = ?", (item['equipment_id'],))
                eq_row = cursor.fetchone()
                if not eq_row:
                    continue
                equipment = dict(eq_row)

            metrics = {'anomalies': 0}
            order_id, order_no = self.create_preventive_order(
                equipment, item['rul_score'], item['health_status'], metrics
            )
            if order_id:
                created += 1

        logger.info(f"共创建 {created} 个预防性维护工单")
        return created

    def get_order(self, order_id):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT wo.*, e.equipment_code, e.name as equipment_name, e.location,
                       eng.name as engineer_name, eng.email as engineer_email
                FROM work_orders wo
                JOIN equipments e ON wo.equipment_id = e.id
                LEFT JOIN engineers eng ON wo.engineer_id = eng.id
                WHERE wo.id = ?
            """, (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_status(self, order_id, new_status, operator='system', note=''):
        if new_status not in self.status_flow:
            logger.error(f"无效的工单状态: {new_status}")
            return False

        order = self.get_order(order_id)
        if not order:
            return False

        current_status = order['status']
        current_idx = self.status_flow.index(current_status) if current_status in self.status_flow else -1
        new_idx = self.status_flow.index(new_status)

        if new_idx <= current_idx and current_idx != -1:
            logger.warning(f"状态回退: {current_status} -> {new_status}")

        try:
            with get_db_cursor(commit=True) as cursor:
                updates = {'status': new_status, 'updated_at': now_str()}

                if new_status == 'in_progress' and not order.get('started_at'):
                    updates['started_at'] = now_str()
                elif new_status == 'completed':
                    updates['completed_at'] = now_str()
                elif new_status == 'verified':
                    updates['verified_at'] = now_str()

                set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
                cursor.execute(f"UPDATE work_orders SET {set_clause} WHERE id = ?",
                               list(updates.values()) + [order_id])

                cursor.execute("""
                    INSERT INTO work_order_status_history
                    (work_order_id, from_status, to_status, changed_by, note)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, current_status, new_status, operator, note))

                if new_status in ('completed', 'verified') and order.get('engineer_id'):
                    cursor.execute("""
                        UPDATE engineers SET workload = GREATEST(workload - 1, 0) WHERE id = ?
                    """, (order['engineer_id'],))

            op_logger.log(
                'update_work_order_status', 'work_order',
                f'工单 {order["order_no"]} 状态变更: {current_status} -> {new_status}',
                equipment_code=order.get('equipment_code')
            )

            logger.info(f"工单 {order['order_no']} 状态更新: {current_status} -> {new_status}")
            return True

        except Exception as e:
            logger.error(f"更新工单状态失败: {e}")
            return False

    def check_timeouts_and_escalate(self):
        escalated = 0
        now = datetime.now()

        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM work_orders
                WHERE status IN ('pending', 'in_progress', 'completed')
                ORDER BY priority DESC, created_at ASC
            """)
            orders = [dict(r) for r in cursor.fetchall()]

        for order in orders:
            status = order['status']

            if status == 'pending':
                check_time = parse_datetime(order['created_at'])
            elif status == 'in_progress':
                check_time = parse_datetime(order.get('assigned_at') or order['created_at'])
            else:
                check_time = parse_datetime(order.get('completed_at'))

            if not check_time:
                continue

            hours_elapsed = (now - check_time).total_seconds() / 3600
            if hours_elapsed >= self.timeout_hours:
                self._escalate_order(order, status, int(hours_elapsed - self.timeout_hours))
                escalated += 1

        if escalated > 0:
            logger.info(f"共升级 {escalated} 个超时工单")
        return escalated

    def _escalate_order(self, order, current_status, hours_overdue):
        try:
            new_level = min(order.get('escalation_level', 0) + 1, 3)

            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    UPDATE work_orders SET escalation_level = ?, updated_at = ? WHERE id = ?
                """, (new_level, now_str(), order['id']))

            NotificationManager.notify_work_order_escalation(order, new_level, current_status, hours_overdue)

            op_logger.log(
                'escalate_work_order', 'work_order',
                f'工单 {order["order_no"]} 升级到级别 {new_level}, 超时 {hours_overdue} 小时'
            )

            logger.warning(f"工单 {order['order_no']} 升级: 级别 {new_level}, 超时 {hours_overdue}h")

        except Exception as e:
            logger.error(f"工单升级失败: {e}")

    def list_orders(self, status=None, priority=None, equipment_id=None, limit=100):
        query = """
            SELECT wo.*, e.equipment_code, e.name as equipment_name,
                   eng.name as engineer_name
            FROM work_orders wo
            JOIN equipments e ON wo.equipment_id = e.id
            LEFT JOIN engineers eng ON wo.engineer_id = eng.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND wo.status = ?"
            params.append(status)
        if priority:
            query += " AND wo.priority = ?"
            params.append(priority)
        if equipment_id:
            query += " AND wo.equipment_id = ?"
            params.append(equipment_id)

        query += " ORDER BY wo.created_at DESC LIMIT ?"
        params.append(limit)

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
