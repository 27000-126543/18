import os
import csv
from datetime import datetime
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import op_logger


class LogQueryManager:
    def __init__(self):
        pass

    def query_logs(self, equipment_code=None, operation_type=None, module=None,
                   start_time=None, end_time=None, operator=None, limit=1000, offset=0):
        query = "SELECT * FROM operation_logs WHERE 1=1"
        params = []

        if equipment_code:
            query += " AND equipment_code = ?"
            params.append(equipment_code)
        if operation_type:
            query += " AND operation_type = ?"
            params.append(operation_type)
        if module:
            query += " AND module = ?"
            params.append(module)
        if operator:
            query += " AND operator = ?"
            params.append(operator)
        if start_time:
            query += " AND created_at >= ?"
            params.append(start_time)
        if end_time:
            query += " AND created_at <= ?"
            params.append(end_time)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def query_work_order_history(self, equipment_code=None, status=None, priority=None,
                                 start_time=None, end_time=None, limit=500):
        query = """
            SELECT wo.*, e.equipment_code, e.name as equipment_name, e.type as equipment_type,
                   e.location, eng.name as engineer_name
            FROM work_orders wo
            JOIN equipments e ON wo.equipment_id = e.id
            LEFT JOIN engineers eng ON wo.engineer_id = eng.id
            WHERE 1=1
        """
        params = []

        if equipment_code:
            query += " AND e.equipment_code = ?"
            params.append(equipment_code)
        if status:
            query += " AND wo.status = ?"
            params.append(status)
        if priority:
            query += " AND wo.priority = ?"
            params.append(priority)
        if start_time:
            query += " AND wo.created_at >= ?"
            params.append(start_time)
        if end_time:
            query += " AND wo.created_at <= ?"
            params.append(end_time)

        query += " ORDER BY wo.created_at DESC LIMIT ?"
        params.append(limit)

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def query_sensor_data(self, equipment_code=None, start_time=None, end_time=None,
                          is_anomaly=None, limit=10000):
        query = """
            SELECT sd.*, e.equipment_code, e.name as equipment_name
            FROM sensor_data sd
            JOIN equipments e ON sd.equipment_id = e.id
            WHERE 1=1
        """
        params = []

        if equipment_code:
            query += " AND e.equipment_code = ?"
            params.append(equipment_code)
        if is_anomaly is not None:
            query += " AND sd.is_anomaly = ?"
            params.append(1 if is_anomaly else 0)
        if start_time:
            query += " AND sd.collection_time >= ?"
            params.append(start_time)
        if end_time:
            query += " AND sd.collection_time <= ?"
            params.append(end_time)

        query += " ORDER BY sd.collection_time DESC LIMIT ?"
        params.append(limit)

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def export_logs_csv(self, filepath, logs):
        if not logs:
            return False
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=list(logs[0].keys()))
                writer.writeheader()
                writer.writerows(logs)
            return True
        except Exception as e:
            logger.error(f"导出日志CSV失败: {e}")
            return False

    def batch_export(self, export_type, output_dir, **filters):
        from config.settings import REPORT_CONFIG
        if not output_dir:
            output_dir = REPORT_CONFIG['report_output_dir']
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if export_type == 'logs':
            data = self.query_logs(**filters)
            filename = f"operation_logs_{timestamp}.csv"
        elif export_type == 'work_orders':
            data = self.query_work_order_history(**filters)
            filename = f"work_orders_{timestamp}.csv"
        elif export_type == 'sensor_data':
            data = self.query_sensor_data(**filters)
            filename = f"sensor_data_{timestamp}.csv"
        else:
            logger.error(f"未知的导出类型: {export_type}")
            return None

        filepath = os.path.join(output_dir, filename)
        success = self.export_logs_csv(filepath, data)

        if success:
            op_logger.log(
                'batch_export', 'system',
                f'批量导出 {export_type}: {len(data)} 条记录 -> {filename}'
            )
            logger.info(f"导出完成: {filepath}, 共 {len(data)} 条记录")
            return filepath
        return None

    def get_operation_types(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT DISTINCT operation_type FROM operation_logs ORDER BY operation_type")
            return [r['operation_type'] for r in cursor.fetchall()]

    def get_modules(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT DISTINCT module FROM operation_logs ORDER BY module")
            return [r['module'] for r in cursor.fetchall()]
