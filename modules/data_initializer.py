import random
from datetime import datetime, timedelta
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import now_str, generate_uuid, json_dumps


class DataInitializer:
    def __init__(self):
        pass

    def seed_sample_data(self):
        logger.info("开始初始化示例数据...")

        self._create_engineers()
        self._create_equipments()
        self._create_spare_parts()
        self._create_suppliers()
        self._create_supplier_parts()
        self._create_historical_sensor_data()
        self._create_sample_work_orders()

        logger.info("示例数据初始化完成!")

    def _create_engineers(self):
        engineers = [
            ('张伟', 'ENG001', '机械维修', '车间A', 'zhangwei@factory.com', '13800000001', 0, 4.8),
            ('李强', 'ENG002', '电气维修', '车间A', 'liqiang@factory.com', '13800000002', 0, 4.6),
            ('王芳', 'ENG003', '机械维修', '车间B', 'wangfang@factory.com', '13800000003', 0, 4.9),
            ('赵刚', 'ENG004', '液压维修', '车间B', 'zhaogang@factory.com', '13800000004', 0, 4.5),
            ('刘洋', 'ENG005', 'general', '车间C', 'liuyang@factory.com', '13800000005', 0, 4.7),
            ('陈明', 'ENG006', '电气维修', '车间C', 'chenming@factory.com', '13800000006', 0, 4.4),
            ('杨丽', 'ENG007', '机械维修', '车间D', 'yangli@factory.com', '13800000007', 0, 4.8),
            ('黄强', 'ENG008', 'general', '车间D', 'huangqiang@factory.com', '13800000008', 0, 4.3),
        ]

        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM engineers")
            if cursor.fetchone()['cnt'] > 0:
                logger.info("工程师数据已存在, 跳过")
                return

            for name, emp_id, specialty, location, email, phone, workload, rating in engineers:
                cursor.execute("""
                    INSERT INTO engineers (name, employee_id, specialty, location, email, phone, workload, rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, emp_id, specialty, location, email, phone, workload, rating))

        logger.info(f"已创建 {len(engineers)} 个工程师")

    def _create_equipments(self):
        equipment_types = ['CNC加工中心', '注塑机', '冲压机', '焊接机器人', '传送带', '空压机', '冷却塔', '包装机']
        locations = ['车间A', '车间B', '车间C', '车间D']
        manufacturers = ['沈阳机床', '海天国际', '济南二机', 'ABB', '西门子', '三菱']
        models = ['VMC850', 'MA3200', 'JH21-160', 'IRB6700', 'SL-100', 'GA75VSD']

        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM equipments")
            if cursor.fetchone()['cnt'] > 0:
                logger.info("设备数据已存在, 跳过")
                return

            for i in range(1, 101):
                eq_type = random.choice(equipment_types)
                location = random.choice(locations)
                manufacturer = random.choice(manufacturers)
                model = random.choice(models)
                install_date = (datetime.now() - timedelta(days=random.randint(100, 2000))).strftime('%Y-%m-%d')
                initial_cost = round(random.uniform(50000, 500000), 2)
                lifespan = random.randint(1800, 5400)

                cursor.execute("""
                    INSERT INTO equipments
                    (equipment_code, name, type, location, manufacturer, model, install_date,
                     status, initial_cost, expected_lifespan_days)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """, (
                    f'EQ{i:05d}', f'{eq_type}-{i:03d}', eq_type, location,
                    manufacturer, model, install_date, initial_cost, lifespan
                ))

        logger.info("已创建 100 台设备")

    def _create_spare_parts(self):
        parts = [
            ('SP001', '主轴轴承', '机械部件', '个', 850.0, 20, 30, 7, '["CNC加工中心"]'),
            ('SP002', '伺服电机', '电气部件', '台', 3200.0, 5, 8, 14, '["CNC加工中心", "注塑机"]'),
            ('SP003', '液压油泵', '液压部件', '台', 1800.0, 8, 12, 10, '["注塑机", "冲压机"]'),
            ('SP004', 'PLC控制器', '电气部件', '台', 2500.0, 5, 6, 14, '["all"]'),
            ('SP005', '冷却风扇', '通用部件', '台', 280.0, 40, 50, 3, '["all"]'),
            ('SP006', '传动皮带', '机械部件', '条', 150.0, 60, 80, 5, '["传送带", "冲压机"]'),
            ('SP007', '焊接枪头', '焊接部件', '个', 1200.0, 10, 15, 10, '["焊接机器人"]'),
            ('SP008', '压力传感器', '传感器', '个', 450.0, 15, 20, 7, '["空压机", "注塑机"]'),
            ('SP009', '温度传感器', '传感器', '个', 180.0, 25, 35, 5, '["all"]'),
            ('SP010', '振动传感器', '传感器', '个', 680.0, 10, 15, 7, '["CNC加工中心", "冲压机"]'),
            ('SP011', '滤芯组件', '过滤部件', '套', 320.0, 30, 40, 5, '["空压机", "冷却塔"]'),
            ('SP012', '润滑油脂', '耗材', '桶', 260.0, 50, 60, 3, '["all"]'),
        ]

        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM spare_parts")
            if cursor.fetchone()['cnt'] > 0:
                logger.info("备件数据已存在, 跳过")
                return

            for code, name, cat, unit, price, safety, current, lead, applicable in parts:
                cursor.execute("""
                    INSERT INTO spare_parts
                    (part_code, name, category, unit, unit_price, safety_stock,
                     current_stock, lead_time_days, applicable_equipment_types)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (code, name, cat, unit, price, safety, current, lead, applicable))

        logger.info(f"已创建 {len(parts)} 个备件")

    def _create_suppliers(self):
        suppliers = [
            ('SUP001', '华科机械设备有限公司', '张经理', 'sales@huake.com', '021-12345678', '上海市浦东新区', 88, 90, 85),
            ('SUP002', '西门子电气授权经销商', '李总', 'siemens@dealer.com', '010-87654321', '北京市朝阳区', 95, 92, 78),
            ('SUP003', '恒力液压元件厂', '王工', 'sales@hengli.com', '0512-55667788', '苏州市工业园区', 85, 82, 90),
            ('SUP004', '优传感科技有限公司', '赵经理', 'sensor@usense.com', '0755-11223344', '深圳市南山区', 90, 88, 86),
            ('SUP005', '通用工业配件商城', '客服部', 'service@indmall.com', '400-888-9999', '广州市天河区', 82, 85, 92),
        ]

        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM suppliers")
            if cursor.fetchone()['cnt'] > 0:
                logger.info("供应商数据已存在, 跳过")
                return

            for code, name, contact, email, phone, addr, q_score, d_score, p_score in suppliers:
                overall = round(q_score * 0.4 + d_score * 0.35 + p_score * 0.25, 2)
                cursor.execute("""
                    INSERT INTO suppliers
                    (supplier_code, name, contact_person, email, phone, address,
                     quality_score, delivery_score, price_score, overall_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (code, name, contact, email, phone, addr, q_score, d_score, p_score, overall))

        logger.info(f"已创建 {len(suppliers)} 个供应商")

    def _create_supplier_parts(self):
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM supplier_parts")
            if cursor.fetchone()['cnt'] > 0:
                logger.info("供应商备件关系已存在, 跳过")
                return

            cursor.execute("SELECT id, unit_price FROM spare_parts")
            parts = [dict(r) for r in cursor.fetchall()]
            cursor.execute("SELECT id FROM suppliers")
            supplier_ids = [r['id'] for r in cursor.fetchall()]

            count = 0
            for part in parts:
                num_suppliers = random.randint(2, 3)
                selected_suppliers = random.sample(supplier_ids, num_suppliers)
                for i, sid in enumerate(selected_suppliers):
                    price_factor = random.uniform(0.9, 1.15)
                    price = round(part['unit_price'] * price_factor, 2)
                    lead = random.randint(3, 21)
                    is_preferred = 1 if i == 0 else 0
                    cursor.execute("""
                        INSERT INTO supplier_parts
                        (supplier_id, part_id, price, lead_time_days, is_preferred)
                        VALUES (?, ?, ?, ?, ?)
                    """, (sid, part['id'], price, lead, is_preferred))
                    count += 1

        logger.info(f"已创建 {count} 个供应商备件关系")

    def _create_historical_sensor_data(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM sensor_data")
            if cursor.fetchone()['cnt'] > 0:
                logger.info("传感器历史数据已存在, 跳过")
                return

            cursor.execute("SELECT id FROM equipments ORDER BY id LIMIT 50")
            equipment_ids = [r['id'] for r in cursor.fetchall()]

        base_values = {
            'temperature': (60.0, 5.0),
            'vibration': (2.5, 0.5),
            'current': (25.0, 3.0),
            'pressure': (6.0, 0.5),
            'rpm': (3000.0, 100.0),
        }

        total_records = 0
        batch_size = 5000

        for eq_id in equipment_ids:
            records = []
            for day_offset in range(30, 0, -1):
                for hour in range(0, 24, 2):
                    collection_time = (
                        datetime.now() - timedelta(days=day_offset, hours=random.randint(0, 1))
                    ).replace(hour=hour, minute=random.randint(0, 59)).strftime('%Y-%m-%d %H:%M:%S')

                    is_anomaly = 1 if random.random() < 0.03 else 0
                    temp = base_values['temperature'][0] + random.gauss(0, base_values['temperature'][1])
                    vib = base_values['vibration'][0] + random.gauss(0, base_values['vibration'][1])
                    curr = base_values['current'][0] + random.gauss(0, base_values['current'][1])
                    press = base_values['pressure'][0] + random.gauss(0, base_values['pressure'][1])
                    rpm = base_values['rpm'][0] + random.gauss(0, base_values['rpm'][1])

                    if is_anomaly:
                        which = random.choice(['temp', 'vib', 'curr'])
                        if which == 'temp':
                            temp = base_values['temperature'][0] + random.choice([-1, 1]) * random.uniform(15, 30)
                        elif which == 'vib':
                            vib = base_values['vibration'][0] + random.choice([-1, 1]) * random.uniform(2, 5)
                        else:
                            curr = base_values['current'][0] + random.choice([-1, 1]) * random.uniform(10, 20)

                    records.append((
                        eq_id,
                        max(0, round(temp, 2)),
                        max(0, round(vib, 4)),
                        max(0, round(curr, 2)),
                        max(0, round(press, 2)),
                        max(0, round(rpm, 1)),
                        collection_time,
                        is_anomaly
                    ))

                    if len(records) >= batch_size:
                        with get_db_cursor(commit=True) as cursor:
                            cursor.executemany("""
                                INSERT INTO sensor_data
                                (equipment_id, temperature, vibration, current, pressure, rpm,
                                 collection_time, is_anomaly)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, records)
                        total_records += len(records)
                        records = []

            if records:
                with get_db_cursor(commit=True) as cursor:
                    cursor.executemany("""
                        INSERT INTO sensor_data
                        (equipment_id, temperature, vibration, current, pressure, rpm,
                         collection_time, is_anomaly)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, records)
                total_records += len(records)

        logger.info(f"已创建 {total_records} 条传感器历史数据")

    def _create_sample_work_orders(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM work_orders")
            if cursor.fetchone()['cnt'] > 0:
                logger.info("工单数据已存在, 跳过")
                return

            cursor.execute("SELECT id, equipment_code FROM equipments ORDER BY id LIMIT 10")
            equipments = [dict(r) for r in cursor.fetchall()]
            cursor.execute("SELECT id FROM engineers ORDER BY id LIMIT 5")
            engineers = [r['id'] for r in cursor.fetchall()]

        count = 0
        priorities = ['high', 'medium', 'low']
        statuses = ['pending', 'in_progress', 'completed', 'verified']

        with get_db_cursor(commit=True) as cursor:
            for i in range(1, 16):
                eq = random.choice(equipments)
                priority = random.choice(priorities)
                status = random.choice(statuses)
                engineer_id = random.choice(engineers) if status != 'pending' else None
                created_at = (datetime.now() - timedelta(days=random.randint(0, 20),
                                                         hours=random.randint(0, 23))).strftime('%Y-%m-%d %H:%M:%S')

                deadline_h = 24 if priority == 'high' else (72 if priority == 'medium' else 168)
                deadline = (datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S') +
                            timedelta(hours=deadline_h)).strftime('%Y-%m-%d %H:%M:%S')

                assigned_at = created_at if engineer_id else None
                started_at = None
                completed_at = None
                verified_at = None

                if status in ['in_progress', 'completed', 'verified']:
                    started_at = (datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S') +
                                  timedelta(hours=random.randint(1, 5))).strftime('%Y-%m-%d %H:%M:%S')
                if status in ['completed', 'verified']:
                    completed_at = (datetime.strptime(started_at, '%Y-%m-%d %H:%M:%S') +
                                    timedelta(hours=random.randint(1, 24))).strftime('%Y-%m-%d %H:%M:%S')
                if status == 'verified':
                    verified_at = (datetime.strptime(completed_at, '%Y-%m-%d %H:%M:%S') +
                                   timedelta(hours=random.randint(1, 12))).strftime('%Y-%m-%d %H:%M:%S')

                cost = round(random.uniform(500, 5000), 2) if status in ['completed', 'verified'] else 0

                cursor.execute("""
                    INSERT INTO work_orders
                    (order_no, equipment_id, title, description, priority, status, engineer_id,
                     assigned_at, deadline, started_at, completed_at, verified_at,
                     maintenance_cost, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f'WO2025{i:05d}', eq['id'],
                    f'预防性维护-{eq["equipment_code"]}',
                    f'设备 {eq["equipment_code"]} 定期检查维护',
                    priority, status, engineer_id,
                    assigned_at, deadline, started_at, completed_at, verified_at,
                    cost, created_at, verified_at or completed_at or started_at or created_at
                ))

                cursor.execute("""
                    INSERT INTO work_order_status_history
                    (work_order_id, from_status, to_status, changed_by, note)
                    VALUES (?, ?, ?, ?, ?)
                """, (i, None, status, 'system', '初始化示例工单'))

                count += 1

        logger.info(f"已创建 {count} 个示例工单")
