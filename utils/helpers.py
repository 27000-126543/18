from datetime import datetime, timedelta
import json
import random
import uuid
from core.logger import logger
from core.database import get_db_cursor


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def today_str():
    return datetime.now().strftime('%Y-%m-%d')


def month_str():
    return datetime.now().strftime('%Y-%m')


def parse_datetime(dt_str):
    if isinstance(dt_str, datetime):
        return dt_str
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
        try:
            return datetime.strptime(dt_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def add_hours(hours):
    return (datetime.now() + timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')


def add_days(days):
    return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')


def days_ago(days):
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')


def generate_order_no(prefix):
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"


def generate_uuid():
    return str(uuid.uuid4())


def safe_float(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]


def json_dumps(data):
    return json.dumps(data, ensure_ascii=False, default=str)


def json_loads(data):
    if not data:
        return {}
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return {}


class OperationLogger:
    @staticmethod
    def log(operation_type, module, description, equipment_code=None, operator='system', ip_address=None):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO operation_logs 
                    (operation_type, module, equipment_code, operator, description, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (operation_type, module, equipment_code, operator, description, ip_address))
            logger.info(f"[{module}] {operation_type}: {description}")
        except Exception as e:
            logger.error(f"记录操作日志失败: {e}")


op_logger = OperationLogger()
