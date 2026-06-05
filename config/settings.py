import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE = {
    'name': 'predictive_maintenance.db',
    'path': os.path.join(BASE_DIR, 'data', 'predictive_maintenance.db'),
}

SENSOR_CONFIG = {
    'metrics': ['temperature', 'vibration', 'current', 'pressure', 'rpm'],
    'default_collection_interval': 60,
    'max_concurrent_collections': 500,
    'batch_size': 1000,
    'baseline_days': 30,
}

HEALTH_CONFIG = {
    'rul_threshold_high_risk': 30,
    'rul_threshold_medium_risk': 60,
    'rul_threshold_low_risk': 90,
    'normal_deviation_factor': 2.0,
}

WORK_ORDER_CONFIG = {
    'high_risk_deadline_hours': 24,
    'medium_risk_deadline_hours': 72,
    'low_risk_deadline_hours': 168,
    'timeout_escalation_hours': 4,
    'status_flow': ['pending', 'in_progress', 'completed', 'verified'],
}

INVENTORY_CONFIG = {
    'safety_stock_factor': 1.5,
    'lead_time_days_default': 7,
    'budget_warning_threshold': 0.8,
}

REPORT_CONFIG = {
    'daily_report_time': '02:00',
    'monthly_report_day': 1,
    'report_output_dir': os.path.join(BASE_DIR, 'reports'),
}

LOGGING_CONFIG = {
    'log_dir': os.path.join(BASE_DIR, 'logs'),
    'log_file': 'system.log',
    'level': 'INFO',
    'max_bytes': 10 * 1024 * 1024,
    'backup_count': 5,
}

SCHEDULER_CONFIG = {
    'data_collection_cron': '* * * * *',
    'health_analysis_cron': '*/30 * * * *',
    'work_order_check_cron': '*/15 * * * *',
    'inventory_check_cron': '0 */6 * * *',
    'daily_report_cron': '0 2 * * *',
    'monthly_report_cron': '0 3 1 * *',
    'escalation_check_cron': '*/10 * * * *',
}

NOTIFICATION_CONFIG = {
    'enabled': True,
    'production_supervisor_email': 'supervisor@factory.com',
    'management_email': 'management@factory.com',
    'escalation_levels': ['engineer', 'supervisor', 'manager', 'director'],
}
