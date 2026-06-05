from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import now_str
from config.settings import NOTIFICATION_CONFIG


class NotificationManager:
    @staticmethod
    def create_notification(notification_type, level, recipient, subject, content,
                            related_type=None, related_id=None):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO notifications 
                    (type, level, recipient, subject, content, related_type, related_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (notification_type, level, recipient, subject, content,
                      related_type, related_id, now_str()))
                notif_id = cursor.lastrowid

                if NOTIFICATION_CONFIG.get('enabled', True):
                    NotificationManager._send_notification(notif_id, recipient, subject, content)
                    cursor.execute("""
                        UPDATE notifications SET is_sent = 1, sent_at = ? WHERE id = ?
                    """, (now_str(), notif_id))

            logger.info(f"通知已创建: {level} - {subject} -> {recipient}")
            return notif_id
        except Exception as e:
            logger.error(f"创建通知失败: {e}")
            return None

    @staticmethod
    def _send_notification(notif_id, recipient, subject, content):
        logger.info(f"[模拟发送] 邮件至 {recipient}: {subject}")
        return True

    @staticmethod
    def notify_work_order_escalation(work_order, level, current_status, hours_overdue):
        level_names = ['工程师', '生产主管', '经理', '总监']
        level_idx = min(level, len(NOTIFICATION_CONFIG['escalation_levels']) - 1)

        if level_idx >= 2:
            recipient = NOTIFICATION_CONFIG['production_supervisor_email']
        else:
            recipient = NOTIFICATION_CONFIG.get('management_email', 'admin@factory.com')

        subject = f"【工单升级】工单 {work_order['order_no']} 已超时 {hours_overdue} 小时"
        content = (f"工单 {work_order['order_no']} 当前状态: {current_status}\n"
                   f"优先级: {work_order.get('priority', 'N/A')}\n"
                   f"已超时: {hours_overdue} 小时\n"
                   f"升级级别: {level_names[level_idx]}\n"
                   f"请及时处理!")

        NotificationManager.create_notification(
            'work_order_escalation', 'high', recipient, subject, content,
            related_type='work_order', related_id=work_order['id']
        )

    @staticmethod
    def notify_low_stock(part, required_qty):
        subject = f"【库存预警】备件 {part['name']} 库存不足"
        content = (f"备件编码: {part['part_code']}\n"
                   f"当前库存: {part['current_stock']}\n"
                   f"安全库存: {part['safety_stock']}\n"
                   f"需求数量: {required_qty}\n"
                   f"请及时补货!")

        NotificationManager.create_notification(
            'low_stock', 'medium', 'inventory@factory.com', subject, content,
            related_type='spare_part', related_id=part['id']
        )

    @staticmethod
    def notify_daily_report_ready(report_date, report_path):
        subject = f"【日报】{report_date} 设备维护管理日报已生成"
        content = f"设备维护管理日报已生成，请查阅。\n报告路径: {report_path}"

        NotificationManager.create_notification(
            'daily_report', 'info', NOTIFICATION_CONFIG['management_email'],
            subject, content
        )

    @staticmethod
    def notify_purchase_approval(requisition):
        subject = f"【审批通知】采购申请 {requisition['req_no']} 需要审批"
        content = (f"采购申请号: {requisition['req_no']}\n"
                   f"预计金额: ¥{requisition.get('estimated_cost', 0):.2f}\n"
                   f"状态: {requisition.get('approval_status', 'pending')}\n"
                   f"请及时审批!")

        NotificationManager.create_notification(
            'purchase_approval', 'medium', 'finance@factory.com', subject, content,
            related_type='purchase_requisition', related_id=requisition['id']
        )

    @staticmethod
    def notify_new_work_order(work_order, engineer=None):
        recipient = engineer['email'] if engineer and engineer.get('email') else 'maintenance@factory.com'
        subject = f"【新工单】{work_order['order_no']} - {work_order['title']}"
        content = (f"工单号: {work_order['order_no']}\n"
                   f"设备: {work_order.get('equipment_code', 'N/A')}\n"
                   f"优先级: {work_order['priority']}\n"
                   f"截止时间: {work_order['deadline']}\n"
                   f"描述: {work_order.get('description', '')}")

        NotificationManager.create_notification(
            'new_work_order', 'high', recipient, subject, content,
            related_type='work_order', related_id=work_order['id']
        )
