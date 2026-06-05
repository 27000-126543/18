import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE = {
    'name': 'predictive_maintenance.db',
    'path': os.path.join(BASE_DIR, 'data', 'predictive_maintenance.db'),
}

WEB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5001,
    'debug': False,
    'secret_key': 'predictive_maintenance_secret_key_2026',
    'session_cookie_name': 'pm_session',
    'permanent_session_lifetime_days': 7,
    'items_per_page': 20,
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
    'monthly_budget': 500000.0,
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
    'use_real_email': True,
    'admin_email': 'admin@factory.com',
    'production_supervisor_email': 'supervisor@factory.com',
    'management_email': 'management@factory.com',
    'inventory_email': 'inventory@factory.com',
    'finance_email': 'finance@factory.com',
    'escalation_levels': ['engineer', 'supervisor', 'manager', 'director'],
}

EMAIL_CONFIG = {
    'smtp_server': 'smtp.qq.com',
    'smtp_port': 465,
    'use_ssl': True,
    'use_tls': False,
    # ================================== 配置说明 ==================================
    # username: 请填入您的完整QQ邮箱地址，例如: '123456789@qq.com'
    # password: 请填入QQ邮箱SMTP授权码（注意：不是QQ登录密码！）
    #           获取方法: 登录QQ邮箱 → 设置 → 账户 → 开启「POP3/SMTP服务」
    #           → 按提示发送短信后即可获取16位授权码
    # 您也可以在Web界面「系统设置 → 邮件配置」中填写并自动保存
    # =============================================================================
    'username': '',
    'password': '',
    'sender_name': '制造业预测性维护系统',
    'max_retries': 3,
    'retry_interval': 5,
    'timeout': 30,
}
