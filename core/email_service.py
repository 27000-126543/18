import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr

from core.logger import logger
from config.settings import EMAIL_CONFIG, NOTIFICATION_CONFIG


class EmailService:
    def __init__(self):
        self.config = EMAIL_CONFIG
        self.notification_config = NOTIFICATION_CONFIG

    def _create_smtp_connection(self):
        """创建SMTP连接"""
        try:
            if self.config.get('use_ssl'):
                smtp = smtplib.SMTP_SSL(
                    self.config['smtp_server'],
                    self.config['smtp_port'],
                    timeout=self.config.get('timeout', 30)
                )
            else:
                smtp = smtplib.SMTP(
                    self.config['smtp_server'],
                    self.config['smtp_port'],
                    timeout=self.config.get('timeout', 30)
                )
                if self.config.get('use_tls'):
                    smtp.starttls()

            smtp.login(self.config['username'], self.config['password'])
            return smtp
        except Exception as e:
            logger.error(f"创建SMTP连接失败: {e}")
            return None

    def _render_html_template(self, template_type, context):
        """渲染HTML邮件模板"""
        templates = {
            'work_order_escalation': self._escalation_email,
            'low_stock': self._low_stock_email,
            'purchase_approval': self._purchase_approval_email,
            'new_work_order': self._new_work_order_email,
            'daily_report': self._daily_report_email,
        }
        renderer = templates.get(template_type, self._default_email)
        return renderer(context)

    def _escalation_email(self, ctx):
        level_names = ['工程师', '生产主管', '部门经理', '总监']
        level_idx = min(ctx.get('level', 0), len(level_names) - 1)
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #ff6b35 0%, #ff4444 100%); padding: 24px; border-radius: 8px 8px 0 0;">
                <h2 style="color: white; margin: 0; font-size: 20px;">⚠️ 工单超时升级通知</h2>
            </div>
            <div style="background: #fff; padding: 24px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                <p style="margin: 0 0 16px 0; color: #1f2937;">
                    工单 <strong>{ctx.get('order_no', '')}</strong> 已超时 <strong>{ctx.get('hours_overdue', 0)} 小时</strong>，已自动升级至 <strong style="color: #ff4444;">{level_names[level_idx]}</strong> 级别处理。
                </p>
                <div style="background: #f9fafb; padding: 16px; border-radius: 6px; margin: 16px 0;">
                    <p style="margin: 4px 0;"><strong>设备：</strong>{ctx.get('equipment_code', '')} - {ctx.get('equipment_name', '')}</p>
                    <p style="margin: 4px 0;"><strong>优先级：</strong><span style="color: #ff4444;">{ctx.get('priority', '')}</span></p>
                    <p style="margin: 4px 0;"><strong>当前状态：</strong>{ctx.get('current_status', '')}</p>
                    <p style="margin: 4px 0;"><strong>截止时间：</strong>{ctx.get('deadline', '')}</p>
                </div>
                <p style="margin: 0; color: #6b7280; font-size: 13px;">请及时登录系统处理，避免影响生产。</p>
            </div>
            <div style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 16px;">
                制造业预测性维护系统 · 自动通知邮件
            </div>
        </div>
        """

    def _low_stock_email(self, ctx):
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 24px; border-radius: 8px 8px 0 0;">
                <h2 style="color: white; margin: 0; font-size: 20px;">📦 备件库存预警</h2>
            </div>
            <div style="background: #fff; padding: 24px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                <p style="margin: 0 0 16px 0; color: #1f2937;">
                    备件 <strong>{ctx.get('part_name', '')}</strong> 库存已低于安全库存阈值，请及时补货。
                </p>
                <div style="background: #fffbeb; border-left: 4px solid #f59e0b; padding: 16px; margin: 16px 0;">
                    <p style="margin: 4px 0;"><strong>备件编码：</strong>{ctx.get('part_code', '')}</p>
                    <p style="margin: 4px 0;"><strong>备件名称：</strong>{ctx.get('part_name', '')}</p>
                    <p style="margin: 4px 0;"><strong>当前库存：</strong><span style="color: #ff4444;">{ctx.get('current_stock', 0)}</span></p>
                    <p style="margin: 4px 0;"><strong>安全库存：</strong>{ctx.get('safety_stock', 0)}</p>
                    <p style="margin: 4px 0;"><strong>建议补货：</strong>{ctx.get('required_qty', 0)} 个</p>
                </div>
                <p style="margin: 0; color: #6b7280; font-size: 13px;">系统已自动生成采购申请，请注意审批。</p>
            </div>
            <div style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 16px;">
                制造业预测性维护系统 · 自动通知邮件
            </div>
        </div>
        """

    def _purchase_approval_email(self, ctx):
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #0066ff 0%, #00d4ff 100%); padding: 24px; border-radius: 8px 8px 0 0;">
                <h2 style="color: white; margin: 0; font-size: 20px;">💰 采购申请审批通知</h2>
            </div>
            <div style="background: #fff; padding: 24px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                <p style="margin: 0 0 16px 0; color: #1f2937;">
                    您有一笔新的采购申请需要审批，该申请金额已超出月度预算 <strong>{ctx.get('budget_pct', '80')}%</strong> 阈值。
                </p>
                <div style="background: #eff6ff; padding: 16px; border-radius: 6px; margin: 16px 0;">
                    <p style="margin: 4px 0;"><strong>申请编号：</strong>{ctx.get('req_no', '')}</p>
                    <p style="margin: 4px 0;"><strong>备件：</strong>{ctx.get('part_name', '')} ({ctx.get('part_code', '')})</p>
                    <p style="margin: 4px 0;"><strong>数量：</strong>{ctx.get('quantity', 0)} 个</p>
                    <p style="margin: 4px 0;"><strong>预估金额：</strong><span style="color: #0066ff; font-size: 18px; font-weight: bold;">¥{ctx.get('estimated_cost', 0):,.2f}</span></p>
                    <p style="margin: 4px 0;"><strong>申请原因：</strong>{ctx.get('reason', '')}</p>
                </div>
                <p style="margin: 0; color: #6b7280; font-size: 13px;">请登录审批工作台进行审核：通过 / 驳回</p>
            </div>
            <div style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 16px;">
                制造业预测性维护系统 · 自动通知邮件
            </div>
        </div>
        """

    def _new_work_order_email(self, ctx):
        priority_colors = {'high': '#ff4444', 'medium': '#f59e0b', 'low': '#10b981'}
        color = priority_colors.get(ctx.get('priority', 'low'), '#10b981')
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, {color} 0%, #1e40af 100%); padding: 24px; border-radius: 8px 8px 0 0;">
                <h2 style="color: white; margin: 0; font-size: 20px;">🔧 新维护工单通知</h2>
            </div>
            <div style="background: #fff; padding: 24px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                <p style="margin: 0 0 16px 0; color: #1f2937;">
                    工程师 <strong>{ctx.get('engineer_name', '')}</strong>，您有一笔新的维护工单已分配。
                </p>
                <div style="background: #f9fafb; padding: 16px; border-radius: 6px; margin: 16px 0;">
                    <p style="margin: 4px 0;"><strong>工单号：</strong>{ctx.get('order_no', '')}</p>
                    <p style="margin: 4px 0;"><strong>标题：</strong>{ctx.get('title', '')}</p>
                    <p style="margin: 4px 0;"><strong>设备：</strong>{ctx.get('equipment_code', '')} - {ctx.get('equipment_name', '')}</p>
                    <p style="margin: 4px 0;"><strong>位置：</strong>{ctx.get('location', '')}</p>
                    <p style="margin: 4px 0;"><strong>优先级：</strong><span style="color: {color}; font-weight: bold;">{ctx.get('priority', '')}</span></p>
                    <p style="margin: 4px 0;"><strong>截止时间：</strong>{ctx.get('deadline', '')}</p>
                </div>
                <p style="margin: 8px 0 0 0; color: #374151; white-space: pre-line;">{ctx.get('description', '')}</p>
            </div>
            <div style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 16px;">
                制造业预测性维护系统 · 自动通知邮件
            </div>
        </div>
        """

    def _daily_report_email(self, ctx):
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #0a1628 0%, #1e3a5f 100%); padding: 24px; border-radius: 8px 8px 0 0;">
                <h2 style="color: #00d4ff; margin: 0; font-size: 20px;">📊 设备维护管理日报</h2>
                <p style="color: #94a3b8; margin: 4px 0 0 0;">{ctx.get('report_date', '')}</p>
            </div>
            <div style="background: #fff; padding: 24px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div style="background: #eff6ff; padding: 16px; border-radius: 6px;">
                        <div style="color: #64748b; font-size: 13px;">设备总数</div>
                        <div style="font-size: 28px; font-weight: bold; color: #1e40af;">{ctx.get('total_equipments', 0)}</div>
                    </div>
                    <div style="background: #fef3c7; padding: 16px; border-radius: 6px;">
                        <div style="color: #92400e; font-size: 13px;">高风险设备</div>
                        <div style="font-size: 28px; font-weight: bold; color: #ff4444;">{ctx.get('high_risk_equipments', 0)}</div>
                    </div>
                    <div style="background: #fef2f2; padding: 16px; border-radius: 6px;">
                        <div style="color: #991b1b; font-size: 13px;">故障率</div>
                        <div style="font-size: 28px; font-weight: bold; color: #ff4444;">{ctx.get('fault_rate', 0):.2f}%</div>
                    </div>
                    <div style="background: #ecfdf5; padding: 16px; border-radius: 6px;">
                        <div style="color: #065f46; font-size: 13px;">维护成本</div>
                        <div style="font-size: 24px; font-weight: bold; color: #10b981;">¥{ctx.get('total_maintenance_cost', 0):,.0f}</div>
                    </div>
                </div>
                <div style="margin-top: 16px;">
                    <p style="margin: 4px 0;"><strong>待处理工单：</strong>{ctx.get('pending_work_orders', 0)} 个</p>
                    <p style="margin: 4px 0;"><strong>已完成工单：</strong>{ctx.get('completed_work_orders', 0)} 个</p>
                    <p style="margin: 4px 0;"><strong>平均修复时间：</strong>{ctx.get('avg_repair_time_hours', 0):.2f} 小时</p>
                    <p style="margin: 4px 0;"><strong>低库存备件：</strong>{ctx.get('low_stock_items', 0)} 个</p>
                </div>
                <p style="margin: 16px 0 0 0; color: #6b7280; font-size: 13px;">详细报告请登录系统查看。</p>
            </div>
            <div style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 16px;">
                制造业预测性维护系统 · 每日自动推送
            </div>
        </div>
        """

    def _default_email(self, ctx):
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
            <h3>系统通知</h3>
            <pre>{str(ctx)}</pre>
        </div>
        """

    def send_email(self, to_email, subject, template_type, context, use_html=True):
        """
        发送邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            template_type: 模板类型
            context: 模板上下文数据
            use_html: 是否使用HTML格式
        
        Returns:
            bool: 是否成功
        """
        if not self.notification_config.get('use_real_email', False):
            logger.info(f"[邮件模拟] 至 {to_email}: {subject}")
            return True

        if not self.config.get('username') or self.config['username'] == 'your_email@qq.com':
            logger.warning("SMTP未配置，跳过真实邮件发送")
            logger.info(f"[邮件模拟] 至 {to_email}: {subject}")
            return True

        max_retries = self.config.get('max_retries', 3)
        retry_interval = self.config.get('retry_interval', 5)

        for attempt in range(1, max_retries + 1):
            try:
                msg = MIMEMultipart('alternative')
                msg['From'] = formataddr(
                    (str(Header(self.config.get('sender_name', '系统通知'), 'utf-8')),
                     self.config['username'])
                )
                msg['To'] = to_email
                msg['Subject'] = Header(subject, 'utf-8')

                body = self._render_html_template(template_type, context)
                if use_html:
                    msg.attach(MIMEText(body, 'html', 'utf-8'))
                else:
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))

                smtp = self._create_smtp_connection()
                if not smtp:
                    raise Exception("SMTP连接失败")

                smtp.sendmail(self.config['username'], [to_email], msg.as_string())
                smtp.quit()

                logger.info(f"邮件发送成功: {to_email} - {subject}")
                return True

            except Exception as e:
                logger.warning(f"邮件发送失败 (第{attempt}/{max_retries}次): {e}")
                if attempt < max_retries:
                    time.sleep(retry_interval * attempt)

        logger.error(f"邮件发送最终失败: {to_email} - {subject}")
        return False


email_service = EmailService()
