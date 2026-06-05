import math
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import now_str, safe_float, safe_int, op_logger
from config.settings import SENSOR_CONFIG


class SensorDataCollector:
    def __init__(self):
        self.max_concurrent = SENSOR_CONFIG['max_concurrent_collections']
        self.batch_size = SENSOR_CONFIG['batch_size']
        self._equipment_cache = None
        self._baseline_cache = {}

    def _load_active_equipments(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, equipment_code, type FROM equipments WHERE status = 'active'")
            self._equipment_cache = [dict(r) for r in cursor.fetchall()]
        return self._equipment_cache

    def _get_equipment_baseline(self, equipment_id):
        cache_key = f"{equipment_id}_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self._baseline_cache:
            return self._baseline_cache[cache_key]

        baseline_days = SENSOR_CONFIG['baseline_days']
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    AVG(temperature) as temp_avg,
                    AVG(vibration) as vib_avg,
                    AVG(current) as curr_avg,
                    AVG(temperature * temperature) as temp_sq_avg,
                    AVG(vibration * vibration) as vib_sq_avg,
                    AVG(current * current) as curr_sq_avg,
                    COUNT(*) as cnt
                FROM sensor_data
                WHERE equipment_id = ? 
                AND collection_time >= datetime('now', '-{baseline_days} days')
            """, (equipment_id,))
            row = cursor.fetchone()
            cnt = safe_int(row['cnt']) if row else 0
            temp_std = math.sqrt(max(0, safe_float(row['temp_sq_avg']) - safe_float(row['temp_avg']) ** 2)) if cnt > 1 else 5.0
            vib_std = math.sqrt(max(0, safe_float(row['vib_sq_avg']) - safe_float(row['vib_avg']) ** 2)) if cnt > 1 else 0.5
            curr_std = math.sqrt(max(0, safe_float(row['curr_sq_avg']) - safe_float(row['curr_avg']) ** 2)) if cnt > 1 else 3.0
            baseline = {
                'temp_avg': safe_float(row['temp_avg'], 60.0),
                'vib_avg': safe_float(row['vib_avg'], 2.5),
                'curr_avg': safe_float(row['curr_avg'], 25.0),
                'temp_std': temp_std or 5.0,
                'vib_std': vib_std or 0.5,
                'curr_std': curr_std or 3.0,
            }
            if baseline['temp_avg'] == 0 or cnt == 0:
                baseline = {'temp_avg': 60.0, 'vib_avg': 2.5, 'curr_avg': 25.0,
                            'temp_std': 5.0, 'vib_std': 0.5, 'curr_std': 3.0}
        self._baseline_cache[cache_key] = baseline
        return baseline

    def _generate_sensor_reading(self, equipment, baseline):
        anomaly_chance = random.random() < 0.02

        temp = baseline['temp_avg'] + random.gauss(0, baseline['temp_std'])
        vib = baseline['vib_avg'] + random.gauss(0, baseline['vib_std'])
        curr = baseline['curr_avg'] + random.gauss(0, baseline['curr_std'])
        pressure = 6.0 + random.gauss(0, 0.5)
        rpm = 3000 + random.gauss(0, 100)

        is_anomaly = 0
        if anomaly_chance:
            factor = random.choice([1.5, 2.0, 2.5, 3.0])
            which = random.choice(['temp', 'vib', 'curr'])
            if which == 'temp':
                temp = baseline['temp_avg'] + baseline['temp_std'] * factor * random.choice([1, -1])
            elif which == 'vib':
                vib = baseline['vib_avg'] + baseline['vib_std'] * factor * random.choice([1, -1])
            else:
                curr = baseline['curr_avg'] + baseline['curr_std'] * factor * random.choice([1, -1])
            is_anomaly = 1

        return (
            equipment['id'],
            max(0, round(temp, 2)),
            max(0, round(vib, 4)),
            max(0, round(curr, 2)),
            max(0, round(pressure, 2)),
            max(0, round(rpm, 1)),
            now_str(),
            is_anomaly
        )

    def collect_from_equipment(self, equipment):
        try:
            baseline = self._get_equipment_baseline(equipment['id'])
            return self._generate_sensor_reading(equipment, baseline)
        except Exception as e:
            logger.error(f"采集设备 {equipment.get('equipment_code')} 数据失败: {e}")
            return None

    def _batch_insert(self, readings):
        if not readings:
            return 0
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.executemany("""
                    INSERT INTO sensor_data 
                    (equipment_id, temperature, vibration, current, pressure, rpm, collection_time, is_anomaly)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, readings)
            return len(readings)
        except Exception as e:
            logger.error(f"批量插入传感器数据失败: {e}")
            return 0

    def collect_all(self):
        start_time = time.time()
        equipments = self._load_active_equipments()
        if not equipments:
            logger.warning("没有活跃设备可供采集")
            return 0

        total_inserted = 0
        batch = []

        logger.info(f"开始采集 {len(equipments)} 台设备的传感器数据...")

        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {executor.submit(self.collect_from_equipment, eq): eq for eq in equipments}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    batch.append(result)
                    if len(batch) >= self.batch_size:
                        total_inserted += self._batch_insert(batch)
                        batch = []

        if batch:
            total_inserted += self._batch_insert(batch)

        elapsed = time.time() - start_time
        logger.info(f"数据采集完成: 共采集 {total_inserted} 条数据, 耗时 {elapsed:.2f} 秒")

        op_logger.log(
            'data_collection', 'sensor',
            f'完成 {len(equipments)} 台设备数据采集, 共 {total_inserted} 条记录'
        )
        return total_inserted

    def get_equipment_recent_data(self, equipment_id, hours=24):
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM sensor_data
                WHERE equipment_id = ? 
                AND collection_time >= datetime('now', '-{hours} hours')
                ORDER BY collection_time DESC
            """, (equipment_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_equipment_stats(self, equipment_id, days=30):
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_count,
                    SUM(is_anomaly) as anomaly_count,
                    AVG(temperature) as temp_avg,
                    AVG(vibration) as vib_avg,
                    AVG(current) as curr_avg,
                    MIN(temperature) as temp_min,
                    MAX(temperature) as temp_max,
                    MIN(vibration) as vib_min,
                    MAX(vibration) as vib_max
                FROM sensor_data
                WHERE equipment_id = ? 
                AND collection_time >= datetime('now', '-{days} days')
            """, (equipment_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
