import random
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import (now_str, generate_order_no, add_days,
                           safe_float, safe_int, op_logger)


class SupplierManager:
    def __init__(self):
        pass

    def get_supplier(self, supplier_id=None, supplier_code=None):
        with get_db_cursor() as cursor:
            if supplier_id:
                cursor.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
            elif supplier_code:
                cursor.execute("SELECT * FROM suppliers WHERE supplier_code = ?", (supplier_code,))
            else:
                return None
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_suppliers(self, active_only=True):
        query = "SELECT * FROM suppliers WHERE 1=1"
        params = []
        if active_only:
            query += " AND status = 'active'"
        query += " ORDER BY overall_score DESC"

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_part_suppliers(self, part_id):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT sp.*, s.name as supplier_name, s.overall_score, s.quality_score,
                       s.delivery_score, s.price_score, s.status as supplier_status
                FROM supplier_parts sp
                JOIN suppliers s ON sp.supplier_id = s.id
                WHERE sp.part_id = ? AND s.status = 'active'
                ORDER BY sp.is_preferred DESC, s.overall_score DESC, sp.price ASC
            """, (part_id,))
            return [dict(r) for r in cursor.fetchall()]

    def allocate_order_shares(self, part_id, total_quantity):
        suppliers = self.get_part_suppliers(part_id)
        if not suppliers:
            logger.warning(f"备件 {part_id} 没有可用供应商")
            return []

        total_score = sum(max(1, s['overall_score']) for s in suppliers)
        allocations = []

        for i, supplier in enumerate(suppliers):
            if i == 0:
                weight = 0.5
            else:
                weight = (max(1, supplier['overall_score']) / total_score) * 0.5

            qty = int(total_quantity * weight)
            if i == 0:
                qty += total_quantity - sum(a['quantity'] for a in allocations) - qty

            if qty > 0:
                allocations.append({
                    'supplier_id': supplier['supplier_id'],
                    'supplier_name': supplier['supplier_name'],
                    'quantity': qty,
                    'unit_price': supplier['price'],
                    'total_amount': round(supplier['price'] * qty, 2),
                    'lead_time_days': supplier['lead_time_days'],
                    'score': supplier['overall_score'],
                })

        remaining = total_quantity - sum(a['quantity'] for a in allocations)
        if remaining > 0 and allocations:
            allocations[0]['quantity'] += remaining
            allocations[0]['total_amount'] = round(allocations[0]['unit_price'] * allocations[0]['quantity'], 2)

        return allocations

    def create_purchase_orders_from_requisition(self, requisition_id):
        from modules.inventory_manager import InventoryManager
        inv_mgr = InventoryManager()

        requisition = inv_mgr.get_requisition(requisition_id)
        if not requisition:
            logger.error(f"采购申请 {requisition_id} 不存在")
            return []

        if requisition['approval_status'] != 'approved':
            logger.warning(f"采购申请 {requisition['req_no']} 未审批通过")
            return []

        allocations = self.allocate_order_shares(requisition['part_id'], requisition['quantity'])
        if not allocations:
            logger.error(f"无法为备件 {requisition.get('part_code')} 分配供应商")
            return []

        created_orders = []
        for alloc in allocations:
            try:
                order_no = generate_order_no('PO')
                expected_delivery = add_days(alloc['lead_time_days'])

                with get_db_cursor(commit=True) as cursor:
                    cursor.execute("""
                        INSERT INTO purchase_orders
                        (order_no, requisition_id, part_id, supplier_id, quantity,
                         unit_price, total_amount, status, expected_delivery, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        order_no, requisition_id, requisition['part_id'],
                        alloc['supplier_id'], alloc['quantity'], alloc['unit_price'],
                        alloc['total_amount'], 'pending', expected_delivery, now_str()
                    ))
                    po_id = cursor.lastrowid

                    cursor.execute("""
                        UPDATE purchase_requisitions SET status = 'processing', updated_at = ?
                        WHERE id = ?
                    """, (now_str(), requisition_id))

                    cursor.execute("""
                        UPDATE suppliers SET total_orders = total_orders + 1 WHERE id = ?
                    """, (alloc['supplier_id'],))

                created_orders.append({
                    'po_id': po_id,
                    'order_no': order_no,
                    'supplier': alloc['supplier_name'],
                    'quantity': alloc['quantity'],
                    'total_amount': alloc['total_amount'],
                })

                op_logger.log(
                    'create_purchase_order', 'supplier',
                    f'创建采购订单 {order_no}, 供应商: {alloc["supplier_name"]}, 金额: ¥{alloc["total_amount"]:.2f}'
                )

            except Exception as e:
                logger.error(f"创建采购订单失败: {e}")

        logger.info(f"为申请 {requisition['req_no']} 创建了 {len(created_orders)} 个采购订单")
        return created_orders

    def update_supplier_score(self, supplier_id, quality_score=None, delivery_score=None, price_score=None):
        supplier = self.get_supplier(supplier_id)
        if not supplier:
            return False

        q = quality_score if quality_score is not None else supplier['quality_score']
        d = delivery_score if delivery_score is not None else supplier['delivery_score']
        p = price_score if price_score is not None else supplier['price_score']

        overall = round((q * 0.4 + d * 0.35 + p * 0.25), 2)

        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    UPDATE suppliers
                    SET quality_score = ?, delivery_score = ?, price_score = ?,
                        overall_score = ?, updated_at = ?
                    WHERE id = ?
                """, (q, d, p, overall, now_str(), supplier_id))

            op_logger.log(
                'update_supplier_score', 'supplier',
                f'更新供应商评分 {supplier.get("supplier_code")}: 综合 {overall}'
            )
            return True
        except Exception as e:
            logger.error(f"更新供应商评分失败: {e}")
            return False

    def process_approved_requisitions(self):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id FROM purchase_requisitions
                WHERE approval_status = 'approved' AND status = 'pending'
            """)
            req_ids = [r['id'] for r in cursor.fetchall()]

        total_orders = 0
        for req_id in req_ids:
            orders = self.create_purchase_orders_from_requisition(req_id)
            total_orders += len(orders)

        if total_orders > 0:
            logger.info(f"处理了 {len(req_ids)} 个采购申请, 创建了 {total_orders} 个订单")
        return total_orders

    def list_purchase_orders(self, status=None):
        query = """
            SELECT po.*, s.name as supplier_name, sp.name as part_name, sp.part_code,
                   pr.req_no
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            JOIN spare_parts sp ON po.part_id = sp.id
            LEFT JOIN purchase_requisitions pr ON po.requisition_id = pr.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND po.status = ?"
            params.append(status)
        query += " ORDER BY po.created_at DESC LIMIT 200"

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
