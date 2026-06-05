from core.logger import logger
from core.database import get_db_cursor
from core.email_service import email_service
from utils.helpers import now_str
from config.settings import NOTIFICATION_CONFIG


class NotificationManager:
    @staticmethod
    def create_notification(notification_type, level, recipient, subject, content,
                            related_type=None, related_id=None, email_context=None):
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
                    sent = NotificationManager._send_notification(
                        notif_id, notification_type, recipient, subject, content, email_context
                    )
                    if sent:
                        cursor.execute("""
                            UPDATE notifications SET is_sent = 1, sent_at = ? WHERE id = ?
                        """, (now_str(), notif_id))

            logger.info(f"通知已创建: {level} - {subject} -> {recipient}")
            return notif_id
        except Exception as e:
            logger.error(f"创建通知失败: {e}")
            return None

    @staticmethod
    def _send_notification(notif_id, notification_type, recipient, subject, content, email_context=None):
        ctx = email_context or {}
        ctx.setdefault('subject', subject)
        ctx.setdefault('content', content)
        sent = email_service.send_email(recipient, subject, notification_type, ctx)
        if not sent:
            logger.info(f"[邮件模拟] 至 {recipient}: {subject}")
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

        email_context = {
            'order_no': work_order['order_no'],
            'equipment_code': work_order.get('equipment_code', ''),
            'equipment_name': work_order.get('equipment_name', ''),
            'priority': work_order.get('priority', 'N/A'),
            'current_status': current_status,
            'hours_overdue': hours_overdue,
            'deadline': work_order.get('deadline', ''),
            'level': level,
        }

        content = (f"工单 {work_order['order_no']} 当前状态: {current_status}\n"
                   f"优先级: {work_order.get('priority', 'N/A')}\n"
                   f"已超时: {hours_overdue} 小时\n"
                   f"升级级别: {level_names[level_idx]}\n"
                   f"请及时处理!")

        NotificationManager.create_notification(
            'work_order_escalation', 'high', recipient, subject, content,
            related_type='work_order', related_id=work_order['id'],
            email_context=email_context
        )

    @staticmethod
    def notify_low_stock(part, required_qty):
        subject = f"【库存预警】备件 {part['name']} 库存不足"

        email_context = {
            'part_code': part['part_code'],
            'part_name': part['name'],
            'current_stock': part['current_stock'],
            'safety_stock': part['safety_stock'],
            'required_qty': required_qty,
        }

        content = (f"备件编码: {part['part_code']}\n"
                   f"当前库存: {part['current_stock']}\n"
                   f"安全库存: {part['safety_stock']}\n"
                   f"需求数量: {required_qty}\n"
                   f"请及时补货!")

        recipient = NOTIFICATION_CONFIG.get('inventory_email', 'inventory@factory.com')
        NotificationManager.create_notification(
            'low_stock', 'medium', recipient, subject, content,
            related_type='spare_part', related_id=part['id'],
            email_context=email_context
        )

    @staticmethod
    def notify_daily_report_ready(report_date, report_path, stats=None):
        subject = f"【日报】{report_date} 设备维护管理日报已生成"

        email_context = stats or {}
        email_context.setdefault('report_date', report_date)

        content = f"设备维护管理日报已生成，请查阅。\n报告路径: {report_path}"

        NotificationManager.create_notification(
            'daily_report', 'info', NOTIFICATION_CONFIG['management_email'],
            subject, content, email_context=email_context
        )

    @staticmethod
    def notify_purchase_approval(requisition, budget_pct='80'):
        subject = f"【审批通知】采购申请 {requisition['req_no']} 需要审批"

        email_context = {
            'req_no': requisition['req_no'],
            'part_code': requisition.get('part_code', ''),
            'part_name': requisition.get('part_name', ''),
            'quantity': requisition.get('quantity', 0),
            'estimated_cost': requisition.get('estimated_cost', 0),
            'reason': requisition.get('reason', ''),
            'budget_pct': budget_pct,
        }

        content = (f"采购申请号: {requisition['req_no']}\n"
                   f"预计金额: ¥{requisition.get('estimated_cost', 0):.2f}\n"
                   f"状态: {requisition.get('approval_status', 'pending')}\n"
                   f"请及时审批!")

        recipient = NOTIFICATION_CONFIG.get('finance_email', 'finance@factory.com')
        NotificationManager.create_notification(
            'purchase_approval', 'medium', recipient, subject, content,
            related_type='purchase_requisition', related_id=requisition['id'],
            email_context=email_context
        )

    @staticmethod
    def notify_new_work_order(work_order, engineer=None):
        recipient = engineer['email'] if engineer and engineer.get('email') else 'maintenance@factory.com'
        subject = f"【新工单】{work_order['order_no']} - {work_order['title']}"

        email_context = {
            'order_no': work_order['order_no'],
            'title': work_order['title'],
            'equipment_code': work_order.get('equipment_code', 'N/A'),
            'equipment_name': work_order.get('equipment_name', ''),
            'location': work_order.get('location', ''),
            'priority': work_order['priority'],
            'deadline': work_order['deadline'],
            'description': work_order.get('description', ''),
            'engineer_name': engineer.get('name', '') if engineer else '',
        }

        content = (f"工单号: {work_order['order_no']}\n"
                   f"设备: {work_order.get('equipment_code', 'N/A')}\n"
                   f"优先级: {work_order['priority']}\n"
                   f"截止时间: {work_order['deadline']}\n"
                   f"描述: {work_order.get('description', '')}")

        NotificationManager.create_notification(
            'new_work_order', 'high', recipient, subject, content,
            related_type='work_order', related_id=work_order['id'],
            email_context=email_context
        )
