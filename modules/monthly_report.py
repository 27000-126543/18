import os
import csv
from datetime import datetime
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import month_str, now_str, today_str, safe_float, safe_int, op_logger
from config.settings import REPORT_CONFIG


class MonthlyReportGenerator:
    def __init__(self):
        self.output_dir = REPORT_CONFIG['report_output_dir']
        os.makedirs(self.output_dir, exist_ok=True)

    def _collect_monthly_stats(self, report_month=None):
        if not report_month:
            report_month = month_str()

        stats = {
            'report_month': report_month,
            'total_equipment_cost': 0.0,
            'total_maintenance_cost': 0.0,
            'total_parts_cost': 0.0,
            'total_lifecycle_cost': 0.0,
            'avg_failure_rate': 0.0,
            'avg_mtbf_hours': 0.0,
            'avg_mttr_hours': 0.0,
            'equipment_utilization': 0.0,
            'equipment_details': [],
        }

        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(initial_cost), 0) as total FROM equipments
                WHERE status != 'scrapped'
            """)
            stats['total_equipment_cost'] = round(safe_float(cursor.fetchone()['total']), 2)

            cursor.execute(f"""
                SELECT COALESCE(SUM(maintenance_cost), 0) as total FROM work_orders
                WHERE strftime('%Y-%m', created_at) = ?
            """, (report_month,))
            stats['total_maintenance_cost'] = round(safe_float(cursor.fetchone()['total']), 2)

            cursor.execute(f"""
                SELECT COALESCE(SUM(total_amount), 0) as total FROM purchase_orders
                WHERE strftime('%Y-%m', created_at) = ? AND status != 'cancelled'
            """, (report_month,))
            stats['total_parts_cost'] = round(safe_float(cursor.fetchone()['total']), 2)

            stats['total_lifecycle_cost'] = round(
                stats['total_equipment_cost'] + stats['total_maintenance_cost'] + stats['total_parts_cost'], 2
            )

            cursor.execute(f"""
                SELECT 
                    AVG(CASE WHEN fault_rate IS NOT NULL THEN fault_rate ELSE 0 END) as avg_fr
                FROM daily_reports
                WHERE strftime('%Y-%m', report_date) = ?
            """, (report_month,))
            stats['avg_failure_rate'] = round(safe_float(cursor.fetchone()['avg_fr']), 2)

            cursor.execute(f"""
                SELECT 
                    COALESCE(AVG((julianday(COALESCE(completed_at, updated_at)) - julianday(created_at)) * 24), 0) as mttr
                FROM work_orders
                WHERE strftime('%Y-%m', created_at) = ?
                AND status IN ('completed', 'verified')
            """, (report_month,))
            stats['avg_mttr_hours'] = round(safe_float(cursor.fetchone()['mttr']), 2)

            stats['avg_mtbf_hours'] = round(720.0 / max(1, (stats['avg_failure_rate'] / 100 + 1)), 2)

            total_equipments = safe_int(cursor.execute(
                "SELECT COUNT(*) as cnt FROM equipments WHERE status = 'active'"
            ).fetchone()['cnt'])
            cursor.execute(f"""
                SELECT COUNT(DISTINCT equipment_id) as fault_eq FROM work_orders
                WHERE strftime('%Y-%m', created_at) = ?
            """, (report_month,))
            fault_eq = safe_int(cursor.fetchone()['fault_eq'])
            if total_equipments > 0:
                stats['equipment_utilization'] = round(
                    (1 - fault_eq / total_equipments) * 100, 2
                )

            cursor.execute(f"""
                SELECT 
                    e.id, e.equipment_code, e.name, e.type, e.location,
                    COALESCE(SUM(wo.maintenance_cost), 0) as maintenance_cost,
                    COUNT(wo.id) as work_order_count,
                    COALESCE(AVG((julianday(COALESCE(wo.completed_at, wo.updated_at)) - julianday(wo.created_at)) * 24), 0) as avg_mttr
                FROM equipments e
                LEFT JOIN work_orders wo ON e.id = wo.equipment_id 
                    AND strftime('%Y-%m', wo.created_at) = ?
                WHERE e.status != 'scrapped'
                GROUP BY e.id
                ORDER BY maintenance_cost DESC
            """, (report_month,))
            stats['equipment_details'] = [dict(r) for r in cursor.fetchall()]

        return stats

    def _generate_text_report(self, stats):
        lines = []
        lines.append("=" * 70)
        lines.append(f"  制造业设备生命周期成本分析月度报告")
        lines.append(f"  报告周期: {stats['report_month']}")
        lines.append("=" * 70)
        lines.append("")
        lines.append("【成本汇总】")
        lines.append(f"  设备原值总额: ¥{stats['total_equipment_cost']:,.2f}")
        lines.append(f"  本月维护成本: ¥{stats['total_maintenance_cost']:,.2f}")
        lines.append(f"  本月备件成本: ¥{stats['total_parts_cost']:,.2f}")
        lines.append(f"  生命周期总成本: ¥{stats['total_lifecycle_cost']:,.2f}")
        lines.append("")
        lines.append("【运行指标】")
        lines.append(f"  平均故障率: {stats['avg_failure_rate']:.2f}%")
        lines.append(f"  平均无故障时间 (MTBF): {stats['avg_mtbf_hours']:.2f} 小时")
        lines.append(f"  平均修复时间 (MTTR): {stats['avg_mttr_hours']:.2f} 小时")
        lines.append(f"  设备利用率: {stats['equipment_utilization']:.2f}%")
        lines.append("")
        lines.append("【设备明细】")
        lines.append(f"  {'设备编号':<15} {'设备名称':<20} {'类型':<10} {'工单数量':>8} {'维护成本':>12} {'MTTR(h)':>8}")
        lines.append("  " + "-" * 75)
        for eq in stats['equipment_details'][:50]:
            lines.append(f"  {eq['equipment_code']:<15} {eq['name'][:20]:<20} {eq['type'][:10]:<10} "
                         f"{eq['work_order_count']:>8} ¥{eq['maintenance_cost']:>10,.2f} {eq['avg_mttr']:>8.2f}")
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"  生成时间: {now_str()}")
        lines.append("=" * 70)
        return '\n'.join(lines)

    def export_csv(self, stats, filepath):
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['指标', '数值'])
                writer.writerow(['报告周期', stats['report_month']])
                writer.writerow(['设备原值总额(¥)', stats['total_equipment_cost']])
                writer.writerow(['本月维护成本(¥)', stats['total_maintenance_cost']])
                writer.writerow(['本月备件成本(¥)', stats['total_parts_cost']])
                writer.writerow(['生命周期总成本(¥)', stats['total_lifecycle_cost']])
                writer.writerow(['平均故障率(%)', stats['avg_failure_rate']])
                writer.writerow(['MTBF(小时)', stats['avg_mtbf_hours']])
                writer.writerow(['MTTR(小时)', stats['avg_mttr_hours']])
                writer.writerow(['设备利用率(%)', stats['equipment_utilization']])
                writer.writerow([])
                writer.writerow(['设备编号', '设备名称', '类型', '位置', '工单数量', '维护成本(¥)', '平均MTTR(小时)'])
                for eq in stats['equipment_details']:
                    writer.writerow([
                        eq['equipment_code'], eq['name'], eq['type'], eq['location'],
                        eq['work_order_count'], eq['maintenance_cost'], round(eq['avg_mttr'], 2)
                    ])
            return True
        except Exception as e:
            logger.error(f"导出CSV失败: {e}")
            return False

    def export_excel(self, stats, filepath):
        try:
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            except ImportError as e:
                logger.error(f"导出月报Excel失败: openpyxl未安装 - {e}")
                return False

            wb = openpyxl.Workbook()

            ws1 = wb.active
            ws1.title = '汇总'

            header_font = Font(bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')

            ws1['A1'] = '制造业设备生命周期成本分析月度报告'
            ws1['A1'].font = Font(bold=True, size=14)
            ws1.merge_cells('A1:B1')

            summary_data = [
                ['报告周期', stats['report_month']],
                ['设备原值总额(¥)', stats['total_equipment_cost']],
                ['本月维护成本(¥)', stats['total_maintenance_cost']],
                ['本月备件成本(¥)', stats['total_parts_cost']],
                ['生命周期总成本(¥)', stats['total_lifecycle_cost']],
                ['平均故障率(%)', stats['avg_failure_rate']],
                ['MTBF(小时)', stats['avg_mtbf_hours']],
                ['MTTR(小时)', stats['avg_mttr_hours']],
                ['设备利用率(%)', stats['equipment_utilization']],
            ]
            for i, row in enumerate(summary_data, start=3):
                ws1.cell(row=i, column=1, value=row[0]).font = Font(bold=True)
                ws1.cell(row=i, column=2, value=row[1])

            ws2 = wb.create_sheet('设备明细')
            headers = ['设备编号', '设备名称', '类型', '位置', '工单数量', '维护成本(¥)', '平均MTTR(小时)']
            for col, header in enumerate(headers, start=1):
                cell = ws2.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center')

            for r, eq in enumerate(stats['equipment_details'], start=2):
                ws2.cell(row=r, column=1, value=eq['equipment_code'])
                ws2.cell(row=r, column=2, value=eq['name'])
                ws2.cell(row=r, column=3, value=eq['type'])
                ws2.cell(row=r, column=4, value=eq['location'])
                ws2.cell(row=r, column=5, value=eq['work_order_count'])
                ws2.cell(row=r, column=6, value=eq['maintenance_cost'])
                ws2.cell(row=r, column=7, value=round(eq['avg_mttr'], 2))

            for col in ws2.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                ws2.column_dimensions[column].width = max_length + 2

            wb.save(filepath)
            return True
        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            return False

    def export_pdf(self, stats, filepath):
        try:
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib import colors
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
            except ImportError as e:
                logger.error(f"导出月报PDF失败: reportlab未安装 - {e}")
                return False

            doc = SimpleDocTemplate(filepath, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, alignment=1)
            elements.append(Paragraph(f"设备生命周期成本分析月度报告", title_style))
            elements.append(Paragraph(f"报告周期: {stats['report_month']}", styles['Heading2']))
            elements.append(Spacer(1, 20))

            summary_data = [
                ['指标', '数值'],
                ['设备原值总额', f"¥{stats['total_equipment_cost']:,.2f}"],
                ['本月维护成本', f"¥{stats['total_maintenance_cost']:,.2f}"],
                ['本月备件成本', f"¥{stats['total_parts_cost']:,.2f}"],
                ['生命周期总成本', f"¥{stats['total_lifecycle_cost']:,.2f}"],
                ['平均故障率', f"{stats['avg_failure_rate']:.2f}%"],
                ['平均无故障时间(MTBF)', f"{stats['avg_mtbf_hours']:.2f} 小时"],
                ['平均修复时间(MTTR)', f"{stats['avg_mttr_hours']:.2f} 小时"],
                ['设备利用率', f"{stats['equipment_utilization']:.2f}%"],
            ]
            summary_table = Table(summary_data, colWidths=[200, 200])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(summary_table)
            elements.append(Spacer(1, 20))

            elements.append(Paragraph("设备明细", styles['Heading2']))
            detail_header = ['设备编号', '设备名称', '类型', '工单数', '维护成本', 'MTTR(h)']
            detail_data = [detail_header]
            for eq in stats['equipment_details'][:30]:
                detail_data.append([
                    eq['equipment_code'], eq['name'][:15], eq['type'],
                    str(eq['work_order_count']), f"¥{eq['maintenance_cost']:,.0f}",
                    f"{eq['avg_mttr']:.1f}"
                ])
            detail_table = Table(detail_data, colWidths=[70, 110, 70, 50, 80, 60])
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(detail_table)
            elements.append(Spacer(1, 20))

            elements.append(Paragraph(f"生成时间: {now_str()}", styles['Normal']))
            doc.build(elements)
            return True
        except Exception as e:
            logger.error(f"导出PDF失败: {e}")
            return False

    def generate_monthly_report(self, report_month=None):
        if not report_month:
            report_month = month_str()

        logger.info(f"开始生成 {report_month} 月度报告...")

        stats = self._collect_monthly_stats(report_month)

        base_name = f"monthly_report_{report_month}"
        pdf_path = os.path.join(self.output_dir, f'{base_name}.pdf')
        excel_path = os.path.join(self.output_dir, f'{base_name}.xlsx')
        text_path = os.path.join(self.output_dir, f'{base_name}.txt')

        text_content = self._generate_text_report(stats)
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

        self.export_pdf(stats, pdf_path)
        self.export_excel(stats, excel_path)

        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO monthly_reports
                    (report_month, total_equipment_cost, total_maintenance_cost, total_parts_cost,
                     total_lifecycle_cost, avg_failure_rate, avg_mtbf_hours, avg_mttr_hours,
                     equipment_utilization, report_path_pdf, report_path_excel)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_month, stats['total_equipment_cost'], stats['total_maintenance_cost'],
                    stats['total_parts_cost'], stats['total_lifecycle_cost'], stats['avg_failure_rate'],
                    stats['avg_mtbf_hours'], stats['avg_mttr_hours'], stats['equipment_utilization'],
                    pdf_path, excel_path
                ))
        except Exception as e:
            logger.error(f"保存月度报告记录失败: {e}")

        op_logger.log(
            'generate_monthly_report', 'report',
            f'生成 {report_month} 月度报告, 生命周期成本 ¥{stats["total_lifecycle_cost"]:,.2f}'
        )

        logger.info(f"月度报告已生成: PDF={pdf_path}, Excel={excel_path}")
        return stats, pdf_path, excel_path

    def get_reports(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM monthly_reports ORDER BY report_month DESC LIMIT 12")
            return [dict(r) for r in cursor.fetchall()]
