import random
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import (now_str, generate_order_no, safe_float,
                           safe_int, op_logger, json_loads, json_dumps)
from config.settings import INVENTORY_CONFIG
from modules.notifications import NotificationManager


class InventoryManager:
    def __init__(self):
        self.safety_stock_factor = INVENTORY_CONFIG['safety_stock_factor']
        self.lead_time_default = INVENTORY_CONFIG['lead_time_days_default']
        self.budget_threshold = INVENTORY_CONFIG['budget_warning_threshold']

    def calculate_safety_stock(self, part_id):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT AVG(quantity) as avg_monthly_usage
                FROM inventory_transactions
                WHERE part_id = ? AND type = 'out'
                AND transaction_date >= date('now', '-90 days')
            """, (part_id,))
            row = cursor.fetchone()
            avg_daily = safe_float(row['avg_monthly_usage'], 0) / 30 if row else 0

            cursor.execute("SELECT lead_time_days, current_stock FROM spare_parts WHERE id = ?",
                           (part_id,))
            part_row = cursor.fetchone()
            if not part_row:
                return 0
            lead_time = safe_int(part_row['lead_time_days'], self.lead_time_default)

        if avg_daily <= 0:
            avg_daily = 1
        safety_stock = int(avg_daily * lead_time * self.safety_stock_factor)
        return max(10, safety_stock)

    def update_all_safety_stocks(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM spare_parts")
            part_ids = [r['id'] for r in cursor.fetchall()]

        updated = 0
        for part_id in part_ids:
            safety_stock = self.calculate_safety_stock(part_id)
            try:
                with get_db_cursor(commit=True) as cursor:
                    cursor.execute("UPDATE spare_parts SET safety_stock = ?, updated_at = ? WHERE id = ?",
                                   (safety_stock, now_str(), part_id))
                updated += 1
            except Exception as e:
                logger.error(f"更新备件 {part_id} 安全库存失败: {e}")

        logger.info(f"更新了 {updated} 个备件的安全库存")
        return updated

    def check_low_stock(self):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM spare_parts
                WHERE current_stock <= safety_stock AND current_stock > 0
                ORDER BY (CAST(current_stock AS REAL) / NULLIF(safety_stock, 0)) ASC
            """)
            low_stock_parts = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM spare_parts WHERE current_stock = 0")
            out_of_stock = [dict(r) for r in cursor.fetchall()]

        all_low = out_of_stock + low_stock_parts
        for part in all_low:
            shortage = max(0, part['safety_stock'] * 2 - part['current_stock'])
            NotificationManager.notify_low_stock(part, shortage)
            existing_req = self._has_pending_requisition(part['id'])
            if not existing_req and shortage > 0:
                self.create_purchase_requisition(part['id'], shortage, '库存不足自动补货')

        logger.info(f"库存检查: {len(low_stock_parts)} 个低库存, {len(out_of_stock)} 个缺货")
        return all_low

    def _has_pending_requisition(self, part_id):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM purchase_requisitions
                WHERE part_id = ? AND status IN ('pending', 'approved')
            """, (part_id,))
            return cursor.fetchone()['cnt'] > 0

    def create_purchase_requisition(self, part_id, quantity, reason, priority='normal', created_by='system'):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM spare_parts WHERE id = ?", (part_id,))
            part = cursor.fetchone()
            if not part:
                logger.error(f"备件 {part_id} 不存在")
                return None

            estimated_cost = safe_float(part['unit_price']) * safe_int(quantity)
            budget_amount = estimated_cost * 1.1
            req_no = generate_order_no('PR')

            approval_status = 'pending'
            monthly_budget = 500000.0
            used_budget = self._get_monthly_used_budget()
            if used_budget + estimated_cost > monthly_budget * self.budget_threshold:
                approval_status = 'needs_approval'

            try:
                cursor.execute("""
                    INSERT INTO purchase_requisitions
                    (req_no, part_id, quantity, estimated_cost, reason, priority,
                     status, budget_amount, approval_status, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    req_no, part_id, quantity, estimated_cost, reason, priority,
                    'pending', budget_amount, approval_status, created_by, now_str(), now_str()
                ))
                req_id = cursor.lastrowid
                cursor.connection.commit()

                requisition = self.get_requisition(req_id)
                if approval_status == 'needs_approval':
                    NotificationManager.notify_purchase_approval(requisition)

                op_logger.log(
                    'create_requisition', 'inventory',
                    f'创建采购申请 {req_no}, 备件: {part["part_code"]}, 数量: {quantity}, 预估: ¥{estimated_cost:.2f}'
                )

                logger.info(f"创建采购申请: {req_no}, 金额: ¥{estimated_cost:.2f}")
                return req_id, req_no

            except Exception as e:
                logger.error(f"创建采购申请失败: {e}")
                cursor.connection.rollback()
                return None

    def _get_monthly_used_budget(self):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(estimated_cost), 0) as total
                FROM purchase_requisitions
                WHERE approval_status IN ('approved', 'completed')
                AND created_at >= date('now', 'start of month')
            """)
            return safe_float(cursor.fetchone()['total'])

    def get_requisition(self, req_id):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT pr.*, sp.name as part_name, sp.part_code, sp.unit_price
                FROM purchase_requisitions pr
                JOIN spare_parts sp ON pr.part_id = sp.id
                WHERE pr.id = ?
            """, (req_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def approve_requisition(self, req_id, approver, approved=True):
        requisition = self.get_requisition(req_id)
        if not requisition:
            return False

        new_status = 'approved' if approved else 'rejected'
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    UPDATE purchase_requisitions
                    SET approval_status = ?, approver = ?, approved_at = ?, updated_at = ?
                    WHERE id = ?
                """, (new_status, approver, now_str() if approved else None, now_str(), req_id))

            op_logger.log(
                'approve_requisition', 'inventory',
                f'采购申请 {requisition["req_no"]} 已{"通过" if approved else "拒绝"}'
            )
            return True
        except Exception as e:
            logger.error(f"审批采购申请失败: {e}")
            return False

    def update_stock(self, part_id, quantity, transaction_type, reference_no=None, operator='system', note=''):
        try:
            with get_db_cursor(commit=True) as cursor:
                if transaction_type == 'in':
                    cursor.execute("""
                        UPDATE spare_parts SET current_stock = current_stock + ?, updated_at = ?
                        WHERE id = ?
                    """, (quantity, now_str(), part_id))
                elif transaction_type == 'out':
                    cursor.execute("""
                        UPDATE spare_parts SET current_stock = GREATEST(current_stock - ?, 0), updated_at = ?
                        WHERE id = ?
                    """, (quantity, now_str(), part_id))

                cursor.execute("""
                    INSERT INTO inventory_transactions
                    (part_id, type, quantity, reference_no, operator, note)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (part_id, transaction_type, quantity, reference_no, operator, note))

            op_logger.log(
                f'stock_{transaction_type}', 'inventory',
                f'库存变动: 备件ID {part_id}, {transaction_type}, 数量 {quantity}'
            )
            return True
        except Exception as e:
            logger.error(f"更新库存失败: {e}")
            return False

    def get_part(self, part_id=None, part_code=None):
        with get_db_cursor() as cursor:
            if part_id:
                cursor.execute("SELECT * FROM spare_parts WHERE id = ?", (part_id,))
            elif part_code:
                cursor.execute("SELECT * FROM spare_parts WHERE part_code = ?", (part_code,))
            else:
                return None
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_parts(self, low_stock_only=False):
        query = "SELECT * FROM spare_parts WHERE 1=1"
        params = []
        if low_stock_only:
            query += " AND current_stock <= safety_stock"
        query += " ORDER BY updated_at DESC"

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def list_requisitions(self, status=None):
        query = """
            SELECT pr.*, sp.name as part_name, sp.part_code
            FROM purchase_requisitions pr
            JOIN spare_parts sp ON pr.part_id = sp.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND pr.approval_status = ?"
            params.append(status)
        query += " ORDER BY pr.created_at DESC LIMIT 200"

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
