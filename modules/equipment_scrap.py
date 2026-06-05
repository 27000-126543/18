from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import now_str, safe_float, safe_int, op_logger, json_loads, json_dumps


class EquipmentScrapManager:
    def __init__(self):
        pass

    def scrap_equipment(self, equipment_id, scrap_reason, residual_value=0, operator='system'):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM equipments WHERE id = ?", (equipment_id,))
            equipment = cursor.fetchone()
            if not equipment:
                logger.error(f"设备 {equipment_id} 不存在")
                return None

            if equipment['status'] == 'scrapped':
                logger.warning(f"设备 {equipment['equipment_code']} 已报废")
                return None

            related_parts = self._find_related_parts(equipment['type'])

            try:
                cursor.execute("""
                    INSERT INTO equipment_scraps
                    (equipment_id, scrap_date, scrap_reason, residual_value,
                     related_parts_disposed, operator, approval_status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'auto_approved', ?)
                """, (
                    equipment_id, now_str(), scrap_reason, residual_value,
                    json_dumps(related_parts), operator, now_str()
                ))

                cursor.execute("""
                    UPDATE equipments
                    SET status = 'scrapped', updated_at = ?
                    WHERE id = ?
                """, (now_str(), equipment_id))

                cursor.connection.commit()

                self._update_related_parts_on_scrap(related_parts)

                op_logger.log(
                    'scrap_equipment', 'equipment',
                    f'设备报废: {equipment["equipment_code"]}, 原因: {scrap_reason}, 残值: ¥{residual_value}',
                    equipment_code=equipment['equipment_code']
                )

                logger.info(f"设备已报废: {equipment['equipment_code']}")
                return {
                    'equipment_id': equipment_id,
                    'equipment_code': equipment['equipment_code'],
                    'related_parts': related_parts,
                }

            except Exception as e:
                logger.error(f"设备报废处理失败: {e}")
                cursor.connection.rollback()
                return None

    def _find_related_parts(self, equipment_type):
        related = []
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, part_code, name, applicable_equipment_types FROM spare_parts")
            parts = [dict(r) for r in cursor.fetchall()]

        for part in parts:
            applicable = json_loads(part.get('applicable_equipment_types', '[]'))
            if isinstance(applicable, str):
                applicable = [applicable]
            if equipment_type in applicable or 'all' in applicable:
                related.append({
                    'part_id': part['id'],
                    'part_code': part['part_code'],
                    'name': part['name'],
                })
        return related

    def _update_related_parts_on_scrap(self, related_parts):
        if not related_parts:
            return
        for part in related_parts:
            logger.info(f"关联备件: {part['part_code']} - {part['name']}")

    def get_scrapped_equipments(self, days=90):
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT es.*, e.equipment_code, e.name as equipment_name, e.type, e.location
                FROM equipment_scraps es
                JOIN equipments e ON es.equipment_id = e.id
                WHERE es.scrap_date >= datetime('now', '-{days} days')
                ORDER BY es.scrap_date DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_active_equipments(self):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM equipments WHERE status = 'active' ORDER BY equipment_code
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_equipment(self, equipment_id=None, equipment_code=None):
        with get_db_cursor() as cursor:
            if equipment_id:
                cursor.execute("SELECT * FROM equipments WHERE id = ?", (equipment_id,))
            elif equipment_code:
                cursor.execute("SELECT * FROM equipments WHERE equipment_code = ?", (equipment_code,))
            else:
                return None
            row = cursor.fetchone()
            return dict(row) if row else None
