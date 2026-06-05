import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.dependency_installer import ensure_web_deps
ensure_web_deps()

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, abort, flash
from datetime import datetime, timedelta

from models.schema import init_database
from modules.sensor_collector import SensorDataCollector
from modules.health_analyzer import HealthAnalyzer
from modules.work_order_manager import WorkOrderManager
from modules.maintenance_verifier import MaintenanceVerifier
from modules.inventory_manager import InventoryManager
from modules.supplier_manager import SupplierManager
from modules.daily_report import DailyReportGenerator
from modules.monthly_report import MonthlyReportGenerator
from modules.equipment_scrap import EquipmentScrapManager
from modules.log_query import LogQueryManager
from modules.data_initializer import DataInitializer
from modules.notifications import NotificationManager
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import today_str, now_str, safe_int, safe_float, parse_datetime
from config.settings import WEB_CONFIG, NOTIFICATION_CONFIG
from core.email_service import email_service


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config['SECRET_KEY'] = WEB_CONFIG['secret_key']
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=WEB_CONFIG['permanent_session_lifetime_days'])
    app.config['JSON_AS_ASCII'] = False
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

    init_database()

    sensor_collector = SensorDataCollector()
    health_analyzer = HealthAnalyzer()
    work_order_mgr = WorkOrderManager()
    verifier = MaintenanceVerifier()
    inventory_mgr = InventoryManager()
    supplier_mgr = SupplierManager()
    daily_report = DailyReportGenerator()
    monthly_report = MonthlyReportGenerator()
    scrap_mgr = EquipmentScrapManager()
    log_query = LogQueryManager()

    app.sensor_collector = sensor_collector
    app.health_analyzer = health_analyzer
    app.work_order_mgr = work_order_mgr
    app.verifier = verifier
    app.inventory_mgr = inventory_mgr
    app.supplier_mgr = supplier_mgr
    app.daily_report = daily_report
    app.monthly_report = monthly_report
    app.scrap_mgr = scrap_mgr
    app.log_query = log_query

    @app.context_processor
    def inject_globals():
        return {
            'now': datetime.now(),
            'today': today_str(),
            'notification_config': NOTIFICATION_CONFIG,
        }

    @app.route('/')
    def dashboard():
        return render_template('dashboard.html', active_page='dashboard')

    @app.route('/api/dashboard/stats')
    def api_dashboard_stats():
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM equipments")
            total_eq = safe_int(cursor.fetchone()['total'])
            cursor.execute("SELECT COUNT(*) as cnt FROM equipments WHERE status = 'active'")
            active_eq = safe_int(cursor.fetchone()['cnt'])

            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN health_status = 'high_risk' THEN 1 ELSE 0 END) as high,
                    SUM(CASE WHEN health_status = 'medium_risk' THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN health_status = 'low_risk' THEN 1 ELSE 0 END) as low,
                    SUM(CASE WHEN health_status = 'normal' THEN 1 ELSE 0 END) as normal
                FROM (
                    SELECT h.equipment_id, h.health_status
                    FROM equipment_health_records h
                    INNER JOIN (
                        SELECT equipment_id, MAX(record_date) as max_date
                        FROM equipment_health_records
                        GROUP BY equipment_id
                    ) latest ON h.equipment_id = latest.equipment_id AND h.record_date = latest.max_date
                )
            """)
            risk_row = cursor.fetchone()
            high_risk = safe_int(risk_row['high'])
            medium_risk = safe_int(risk_row['medium'])
            low_risk = safe_int(risk_row['low'])
            normal_risk = safe_int(risk_row['normal'])
            if high_risk + medium_risk + low_risk + normal_risk == 0:
                normal_risk = active_eq

            cursor.execute("""
                SELECT status, COUNT(*) as cnt FROM work_orders
                WHERE status IN ('pending', 'in_progress', 'completed', 'verified')
                GROUP BY status
            """)
            wo_stats = {r['status']: safe_int(r['cnt']) for r in cursor.fetchall()}

            cursor.execute("SELECT rul_score FROM equipment_health_records h "
                           "INNER JOIN (SELECT equipment_id, MAX(record_date) as md "
                           "FROM equipment_health_records GROUP BY equipment_id) l "
                           "ON h.equipment_id = l.equipment_id AND h.record_date = l.md")
            rul_scores = [safe_float(r['rul_score']) for r in cursor.fetchall()]

            rul_distribution = [0] * 10
            for s in rul_scores:
                if s >= 100:
                    idx = 9
                else:
                    idx = min(9, int(s // 10))
                rul_distribution[idx] += 1

            cursor.execute("""
                SELECT s.*, e.equipment_code, e.name as equipment_name
                FROM sensor_data s
                JOIN equipments e ON s.equipment_id = e.id
                WHERE s.is_anomaly = 1
                ORDER BY s.collection_time DESC
                LIMIT 15
            """)
            anomalies = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT *,
                    CASE WHEN current_stock = 0 OR safety_stock = 0 THEN 0
                         ELSE ROUND(CAST(current_stock AS REAL) / safety_stock * 100, 1)
                    END as stock_pct
                FROM spare_parts
                WHERE safety_stock > 0 AND current_stock <= safety_stock
                ORDER BY CASE WHEN safety_stock = 0 THEN 0
                              ELSE CAST(current_stock AS REAL) / safety_stock END ASC
                LIMIT 10
            """)
            low_stock = [dict(r) for r in cursor.fetchall()]

        return jsonify({
            'total_equipments': total_eq,
            'active_equipments': active_eq,
            'risk_distribution': {
                'high': high_risk, 'medium': medium_risk,
                'low': low_risk, 'normal': normal_risk
            },
            'work_order_stats': {
                'pending': wo_stats.get('pending', 0),
                'in_progress': wo_stats.get('in_progress', 0),
                'completed': wo_stats.get('completed', 0),
                'verified': wo_stats.get('verified', 0),
            },
            'rul_distribution': rul_distribution,
            'anomalies': anomalies,
            'low_stock': low_stock,
        })

    @app.route('/api/sensor/realtime/<int:equipment_id>')
    def api_sensor_realtime(equipment_id):
        hours = safe_int(request.args.get('hours', 24))
        data = sensor_collector.get_equipment_recent_data(equipment_id, hours=hours)
        data.reverse()
        result = {
            'times': [r['collection_time'] for r in data],
            'temperature': [safe_float(r['temperature']) for r in data],
            'vibration': [safe_float(r['vibration']) for r in data],
            'current': [safe_float(r['current']) for r in data],
        }
        return jsonify(result)

    @app.route('/api/equipments/list')
    def api_equipments_list():
        keyword = request.args.get('keyword', '').strip()
        with get_db_cursor() as cursor:
            query = """
                SELECT e.*, h.rul_score, h.health_status
                FROM equipments e
                LEFT JOIN equipment_health_records h ON e.id = h.equipment_id
                LEFT JOIN (
                    SELECT equipment_id, MAX(record_date) as max_date
                    FROM equipment_health_records GROUP BY equipment_id
                ) l ON h.equipment_id = l.equipment_id AND h.record_date = l.max_date
                WHERE e.status != 'scrapped'
            """
            params = []
            if keyword:
                query += " AND (e.equipment_code LIKE ? OR e.name LIKE ? OR e.location LIKE ?)"
                kw = f"%{keyword}%"
                params.extend([kw, kw, kw])
            query += " ORDER BY h.rul_score ASC NULLS LAST LIMIT 200"
            cursor.execute(query, params)
            equipments = [dict(r) for r in cursor.fetchall()]
        return jsonify(equipments)

    @app.route('/work_orders')
    def work_orders():
        return render_template('work_orders/list.html', active_page='work_orders')

    @app.route('/api/work_orders')
    def api_work_orders():
        status = request.args.get('status')
        priority = request.args.get('priority')
        page = safe_int(request.args.get('page', 1))
        page_size = WEB_CONFIG['items_per_page']

        with get_db_cursor() as cursor:
            where = "WHERE 1=1"
            params = []
            if status:
                where += " AND wo.status = ?"
                params.append(status)
            if priority:
                where += " AND wo.priority = ?"
                params.append(priority)

            cursor.execute(f"""
                SELECT COUNT(*) as total FROM work_orders wo {where}
            """, params)
            total = safe_int(cursor.fetchone()['total'])

            offset = (page - 1) * page_size
            cursor.execute(f"""
                SELECT wo.*, e.equipment_code, e.name as equipment_name, e.location,
                       eng.name as engineer_name, eng.email as engineer_email
                FROM work_orders wo
                JOIN equipments e ON wo.equipment_id = e.id
                LEFT JOIN engineers eng ON wo.engineer_id = eng.id
                {where}
                ORDER BY wo.created_at DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset])
            orders = [dict(r) for r in cursor.fetchall()]

        return jsonify({
            'total': total,
            'page': page,
            'page_size': page_size,
            'orders': orders,
        })

    @app.route('/work_orders/<int:order_id>')
    def work_order_detail(order_id):
        order = work_order_mgr.get_order(order_id)
        if not order:
            abort(404)
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM work_order_status_history
                WHERE work_order_id = ? ORDER BY changed_at
            """, (order_id,))
            history = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM engineers ORDER BY name")
            engineers = [dict(r) for r in cursor.fetchall()]

        return render_template('work_orders/detail.html',
                               order=order, history=history,
                               engineers=engineers, active_page='work_orders')

    @app.route('/work_orders/<int:order_id>/status', methods=['POST'])
    def api_update_work_order_status(order_id):
        new_status = request.form.get('status')
        operator = request.form.get('operator', 'web_user')
        note = request.form.get('note', '')
        engineer_id = request.form.get('engineer_id')

        if engineer_id:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    UPDATE work_orders SET engineer_id = ?, assigned_at = ?,
                    status = 'in_progress', updated_at = ? WHERE id = ?
                """, (safe_int(engineer_id), now_str(), now_str(), order_id))
                cursor.execute("""
                    INSERT INTO work_order_status_history
                    (work_order_id, from_status, to_status, changed_by, note)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, 'pending', 'in_progress', operator, note))

        success = work_order_mgr.update_status(order_id, new_status, operator, note)
        return jsonify({'success': success})

    @app.route('/work_orders/create', methods=['GET', 'POST'])
    def create_work_order():
        if request.method == 'POST':
            equipment_id = safe_int(request.form.get('equipment_id'))
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            priority = request.form.get('priority', 'low')

            with get_db_cursor() as cursor:
                cursor.execute("SELECT * FROM equipments WHERE id = ?", (equipment_id,))
                eq_row = cursor.fetchone()
                if not eq_row:
                    return jsonify({'success': False, 'error': '设备不存在'})
                equipment = dict(eq_row)

            rul_score = safe_float(request.form.get('rul_score', 70))
            health_status = request.form.get('health_status', 'low_risk')
            order_id, order_no = work_order_mgr.create_preventive_order(
                equipment, rul_score, health_status, {}
            )
            if order_id:
                return redirect(url_for('work_order_detail', order_id=order_id))

        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, equipment_code, name, location FROM equipments WHERE status = 'active' ORDER BY equipment_code")
            equipments = [dict(r) for r in cursor.fetchall()]
        return render_template('work_orders/create.html',
                               equipments=equipments, active_page='work_orders')

    @app.route('/inventory')
    def inventory():
        return render_template('inventory/list.html', active_page='inventory')

    @app.route('/api/inventory/parts')
    def api_inventory_parts():
        low_only = request.args.get('low_only') == 'true'
        parts = inventory_mgr.list_parts(low_stock_only=low_only)
        return jsonify({'parts': parts})

    @app.route('/inventory/transaction', methods=['POST'])
    def api_inventory_transaction():
        part_id = safe_int(request.form.get('part_id'))
        trans_type = request.form.get('type')
        quantity = safe_int(request.form.get('quantity'))
        operator = request.form.get('operator', 'web_user')
        note = request.form.get('note', '')
        ref_no = request.form.get('reference_no')

        success = inventory_mgr.update_stock(part_id, quantity, trans_type, ref_no, operator, note)
        return jsonify({'success': success})

    @app.route('/api/inventory/transactions')
    def api_inventory_transactions():
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT t.*, sp.name as part_name, sp.part_code
                FROM inventory_transactions t
                JOIN spare_parts sp ON t.part_id = sp.id
                ORDER BY t.transaction_date DESC LIMIT 100
            """)
            return jsonify([dict(r) for r in cursor.fetchall()])

    @app.route('/approval')
    def approval_center():
        return render_template('approval/list.html', active_page='approval')

    @app.route('/api/approval/list')
    def api_approval_list():
        status = request.args.get('status', 'needs_approval')
        reqs = inventory_mgr.list_requisitions(status=status)
        return jsonify({'requisitions': reqs})

    @app.route('/approval/<int:req_id>/approve', methods=['POST'])
    def api_approve_requisition(req_id):
        approver = request.form.get('approver', 'web_approver')
        note = request.form.get('note', '')
        success = inventory_mgr.approve_requisition(req_id, approver, True)
        if success:
            supplier_mgr.process_approved_requisitions()
        return jsonify({'success': success})

    @app.route('/approval/<int:req_id>/reject', methods=['POST'])
    def api_reject_requisition(req_id):
        approver = request.form.get('approver', 'web_approver')
        note = request.form.get('note', '')
        success = inventory_mgr.approve_requisition(req_id, approver, False)
        return jsonify({'success': success})

    @app.route('/reports')
    def reports():
        return render_template('reports/index.html', active_page='reports')

    @app.route('/reports/daily')
    def reports_daily():
        date = request.args.get('date', today_str())
        stats = daily_report._collect_daily_stats(date)
        recent = daily_report.get_recent_reports(days=14)
        return render_template('reports/daily.html',
                               stats=stats, report_date=date,
                               recent_reports=recent, active_page='reports')

    @app.route('/reports/daily/export/<fmt>')
    def export_daily_report(fmt):
        from utils.dependency_installer import ensure_excel_deps, ensure_pdf_deps
        date = request.args.get('date', today_str())
        report_dir = app.config.get('REPORT_DIR', 'reports')
        os.makedirs(report_dir, exist_ok=True)

        if fmt == 'excel':
            if not ensure_excel_deps():
                return "openpyxl安装失败，请安装后重试", 500
            stats = daily_report._collect_daily_stats(date)
            filepath = os.path.join(report_dir, f'daily_report_{date}.xlsx')
            ok = daily_report.export_excel(stats, filepath)
            if not ok or not os.path.exists(filepath):
                return "Excel导出失败，请查看日志", 500
            return send_file(filepath, as_attachment=True,
                             download_name=f'daily_report_{date}.xlsx',
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        elif fmt == 'pdf':
            if not ensure_pdf_deps():
                return "reportlab安装失败，请安装后重试", 500
            stats = daily_report._collect_daily_stats(date)
            filepath = os.path.join(report_dir, f'daily_report_{date}.pdf')
            ok = daily_report.export_pdf(stats, filepath)
            if not ok or not os.path.exists(filepath):
                return "PDF导出失败，请查看日志", 500
            return send_file(filepath, as_attachment=True,
                             download_name=f'daily_report_{date}.pdf',
                             mimetype='application/pdf')

        abort(404)

    @app.route('/reports/monthly')
    def reports_monthly():
        from utils.helpers import month_str
        month = request.args.get('month', month_str())
        stats = monthly_report._collect_monthly_stats(month)
        reports_list = monthly_report.get_reports()
        return render_template('reports/monthly.html',
                               stats=stats, report_month=month,
                               reports=reports_list, active_page='reports')

    @app.route('/reports/monthly/export/<fmt>')
    def export_monthly_report(fmt):
        from utils.dependency_installer import ensure_excel_deps, ensure_pdf_deps
        from utils.helpers import month_str
        month = request.args.get('month', month_str())
        report_dir = app.config.get('REPORT_DIR', 'reports')
        os.makedirs(report_dir, exist_ok=True)

        if fmt == 'excel':
            if not ensure_excel_deps():
                return "openpyxl安装失败，请安装后重试", 500
            stats = monthly_report._collect_monthly_stats(month)
            filepath = os.path.join(report_dir, f'monthly_report_{month}.xlsx')
            ok = monthly_report.export_excel(stats, filepath)
            if not ok or not os.path.exists(filepath):
                return "Excel导出失败，请查看日志", 500
            return send_file(filepath, as_attachment=True,
                             download_name=f'monthly_report_{month}.xlsx',
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        elif fmt == 'pdf':
            if not ensure_pdf_deps():
                return "reportlab安装失败，请安装后重试", 500
            stats = monthly_report._collect_monthly_stats(month)
            filepath = os.path.join(report_dir, f'monthly_report_{month}.pdf')
            ok = monthly_report.export_pdf(stats, filepath)
            if not ok or not os.path.exists(filepath):
                return "PDF导出失败，请查看日志", 500
            return send_file(filepath, as_attachment=True,
                             download_name=f'monthly_report_{month}.pdf',
                             mimetype='application/pdf')
        abort(404)

    @app.route('/equipment')
    def equipment_list():
        return render_template('equipment/list.html', active_page='equipment')

    @app.route('/equipment/<int:eq_id>')
    def equipment_detail(eq_id):
        eq = scrap_mgr.get_equipment(eq_id)
        if not eq:
            abort(404)
        health_history = health_analyzer.get_equipment_health_history(eq_id, days=30)
        recent_data = sensor_collector.get_equipment_recent_data(eq_id, hours=48)
        stats = sensor_collector.get_equipment_stats(eq_id, days=30)
        return render_template('equipment/detail.html',
                               equipment=eq, health_history=health_history,
                               recent_data=recent_data[:100], stats=stats,
                               active_page='equipment')

    @app.route('/equipment/scrap', methods=['POST'])
    def api_scrap_equipment():
        eq_id = safe_int(request.form.get('equipment_id'))
        reason = request.form.get('reason', '').strip()
        residual = safe_float(request.form.get('residual_value', 0))
        operator = request.form.get('operator', 'web_user')
        result = scrap_mgr.scrap_equipment(eq_id, reason, residual, operator)
        return jsonify({'success': result is not None})

    @app.route('/logs')
    def logs_page():
        return render_template('logs/list.html', active_page='logs')

    @app.route('/api/logs')
    def api_logs():
        equipment_code = request.args.get('equipment_code')
        operation_type = request.args.get('operation_type')
        module = request.args.get('module')
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        page = safe_int(request.args.get('page', 1))
        page_size = WEB_CONFIG['items_per_page']

        with get_db_cursor() as cursor:
            where = "WHERE 1=1"
            params = []
            if equipment_code:
                where += " AND equipment_code = ?"
                params.append(equipment_code)
            if operation_type:
                where += " AND operation_type = ?"
                params.append(operation_type)
            if module:
                where += " AND module = ?"
                params.append(module)
            if start_time:
                where += " AND created_at >= ?"
                params.append(start_time)
            if end_time:
                where += " AND created_at <= ?"
                params.append(end_time)

            cursor.execute(f"SELECT COUNT(*) as total FROM operation_logs {where}", params)
            total = safe_int(cursor.fetchone()['total'])

            offset = (page - 1) * page_size
            cursor.execute(f"""
                SELECT * FROM operation_logs {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            """, params + [page_size, offset])
            logs = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT DISTINCT operation_type FROM operation_logs ORDER BY operation_type")
            op_types = [r['operation_type'] for r in cursor.fetchall()]
            cursor.execute("SELECT DISTINCT module FROM operation_logs ORDER BY module")
            modules = [r['module'] for r in cursor.fetchall()]

        return jsonify({
            'total': total, 'page': page, 'page_size': page_size,
            'logs': logs, 'operation_types': op_types, 'modules': modules
        })

    @app.route('/logs/export')
    def export_logs():
        filepath = log_query.batch_export('logs', None,
                                           equipment_code=request.args.get('equipment_code'),
                                           operation_type=request.args.get('operation_type'),
                                           module=request.args.get('module'))
        if filepath and os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        return "导出失败", 500

    @app.route('/api/trigger/collect', methods=['POST'])
    def api_trigger_collect():
        count = sensor_collector.collect_all()
        return jsonify({'count': count})

    @app.route('/api/trigger/health_analysis', methods=['POST'])
    def api_trigger_health():
        results, high_risk = health_analyzer.analyze_all_equipments()
        if high_risk:
            work_order_mgr.create_orders_for_high_risk(high_risk)
        return jsonify({'analyzed': len(results), 'high_risk': len(high_risk)})

    @app.route('/api/email/test', methods=['GET', 'POST'])
    def api_email_test():
        to_email = request.args.get('to') or request.form.get('to')
        success, message = email_service.send_test_email(to_email)
        return jsonify({'success': success, 'message': message})

    @app.route('/suppliers')
    def suppliers():
        suppliers_list = supplier_mgr.list_suppliers()
        purchase_orders = supplier_mgr.list_purchase_orders()
        return render_template('suppliers/list.html',
                               suppliers=suppliers_list,
                               purchase_orders=purchase_orders,
                               active_page='suppliers')

    return app


def main():
    app = create_app()

    try:
        initializer = DataInitializer()
        initializer.seed_sample_data()
    except Exception as e:
        logger.warning(f"初始化示例数据可能已存在: {e}")

    print()
    print("=" * 70)
    print("  制造业生产设备预测性维护与备件智能管理系统 - Web版")
    print("=" * 70)
    print()
    print(f"  访问地址: http://{WEB_CONFIG['host']}:{WEB_CONFIG['port']}")
    print(f"  调试模式: {'开启' if WEB_CONFIG['debug'] else '关闭'}")
    print()
    print("  邮件配置说明:")
    print(f"    当前状态: {'真实邮件模式' if NOTIFICATION_CONFIG.get('use_real_email') else '模拟模式'}")
    from config.settings import EMAIL_CONFIG
    if EMAIL_CONFIG.get('username') and EMAIL_CONFIG['username'] != 'your_email@qq.com':
        print(f"    发件账号: {EMAIL_CONFIG['username']}")
    else:
        print("    ⚠️  发件账号未配置! 请编辑 config/settings.py 中 EMAIL_CONFIG.username")
    if EMAIL_CONFIG.get('password') and EMAIL_CONFIG['password'] != 'your_smtp_auth_code':
        print("    SMTP授权码: 已配置 ✓")
    else:
        print("    ⚠️  SMTP授权码未配置! 请编辑 config/settings.py 中 EMAIL_CONFIG.password")
    print()

    if NOTIFICATION_CONFIG.get('use_real_email'):
        print("  📧 正在发送启动测试邮件...")
        test_ok, test_msg = email_service.send_test_email()
        if test_ok:
            print(f"    ✓ {test_msg}")
        else:
            print(f"    ✗ {test_msg}")
            print("    提示: 点击Web界面右上角「测试邮件」按钮可随时重试")
        print()

    print("  按 Ctrl+C 停止服务器")
    print()

    app.run(host=WEB_CONFIG['host'],
            port=WEB_CONFIG['port'],
            debug=WEB_CONFIG['debug'],
            use_reloader=False,
            threaded=True)


if __name__ == '__main__':
    main()
