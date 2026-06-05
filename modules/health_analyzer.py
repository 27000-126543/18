import math
from datetime import datetime, timedelta
from core.logger import logger
from core.database import get_db_cursor
from utils.helpers import now_str, today_str, safe_float, safe_int, op_logger
from config.settings import HEALTH_CONFIG, SENSOR_CONFIG


class HealthAnalyzer:
    def __init__(self):
        self.high_risk_threshold = HEALTH_CONFIG['rul_threshold_high_risk']
        self.medium_risk_threshold = HEALTH_CONFIG['rul_threshold_medium_risk']
        self.low_risk_threshold = HEALTH_CONFIG['rul_threshold_low_risk']
        self.deviation_factor = HEALTH_CONFIG['normal_deviation_factor']

    def _get_baseline_stats(self, equipment_id):
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
                    AVG(is_anomaly) as anomaly_rate,
                    COUNT(*) as cnt
                FROM sensor_data
                WHERE equipment_id = ? 
                AND collection_time >= datetime('now', '-{baseline_days} days')
            """, (equipment_id,))
            row = cursor.fetchone()

            if not row or row['temp_avg'] is None or safe_int(row['cnt']) == 0:
                return {
                    'temp_avg': 60.0, 'vib_avg': 2.5, 'curr_avg': 25.0,
                    'temp_std': 5.0, 'vib_std': 0.5, 'curr_std': 3.0,
                    'anomaly_rate': 0.0
                }

            cnt = safe_int(row['cnt'])
            temp_std = math.sqrt(max(0, safe_float(row['temp_sq_avg']) - safe_float(row['temp_avg']) ** 2)) if cnt > 1 else 5.0
            vib_std = math.sqrt(max(0, safe_float(row['vib_sq_avg']) - safe_float(row['vib_avg']) ** 2)) if cnt > 1 else 0.5
            curr_std = math.sqrt(max(0, safe_float(row['curr_sq_avg']) - safe_float(row['curr_avg']) ** 2)) if cnt > 1 else 3.0

            return {
                'temp_avg': safe_float(row['temp_avg'], 60.0),
                'vib_avg': safe_float(row['vib_avg'], 2.5),
                'curr_avg': safe_float(row['curr_avg'], 25.0),
                'temp_std': temp_std or 5.0,
                'vib_std': vib_std or 0.5,
                'curr_std': curr_std or 3.0,
                'anomaly_rate': safe_float(row['anomaly_rate'], 0.0),
            }

    def _get_recent_stats(self, equipment_id, hours=24):
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    AVG(temperature) as temp_avg,
                    AVG(vibration) as vib_avg,
                    AVG(current) as curr_avg,
                    SUM(is_anomaly) as anomaly_count,
                    COUNT(*) as total_count
                FROM sensor_data
                WHERE equipment_id = ? 
                AND collection_time >= datetime('now', '-{hours} hours')
            """, (equipment_id,))
            row = cursor.fetchone()

            if not row or row['total_count'] is None or safe_int(row['total_count']) == 0:
                return None

            return {
                'temp_avg': safe_float(row['temp_avg']),
                'vib_avg': safe_float(row['vib_avg']),
                'curr_avg': safe_float(row['curr_avg']),
                'anomaly_count': safe_int(row['anomaly_count']),
                'total_count': safe_int(row['total_count']),
            }

    def _calculate_metric_deviation_score(self, current_val, baseline_avg, baseline_std):
        if baseline_std == 0:
            return 100.0 if current_val else 0
        z_score = abs(current_val - baseline_avg) / baseline_std
        if z_score <= 1:
            return 100.0
        elif z_score <= 2:
            return 85.0 - (z_score - 1) * 15.0
        elif z_score <= 3:
            return 70.0 - (z_score - 2) * 15.0
        else:
            return max(0.0, 55.0 - (z_score - 3) * 10.0)

    def _calculate_anomaly_score(self, recent_stats):
        if not recent_stats or recent_stats['total_count'] == 0:
            return 100.0
        anomaly_rate = recent_stats['anomaly_count'] / recent_stats['total_count']
        if anomaly_rate <= 0.01:
            return 100.0
        elif anomaly_rate <= 0.05:
            return 85.0
        elif anomaly_rate <= 0.1:
            return 70.0
        elif anomaly_rate <= 0.2:
            return 50.0
        else:
            return max(0.0, 30.0 - (anomaly_rate - 0.2) * 100)

    def calculate_rul_score(self, equipment_id):
        baseline = self._get_baseline_stats(equipment_id)
        recent = self._get_recent_stats(equipment_id, hours=24)

        if not recent:
            recent = self._get_recent_stats(equipment_id, hours=72)
        if not recent:
            return 85.0, 'normal', baseline

        temp_score = self._calculate_metric_deviation_score(
            recent['temp_avg'], baseline['temp_avg'], baseline['temp_std'])
        vib_score = self._calculate_metric_deviation_score(
            recent['vib_avg'], baseline['vib_avg'], baseline['vib_std'])
        curr_score = self._calculate_metric_deviation_score(
            recent['curr_avg'], baseline['curr_avg'], baseline['curr_std'])
        anomaly_score = self._calculate_anomaly_score(recent)

        weights = {'temp': 0.3, 'vib': 0.35, 'curr': 0.2, 'anomaly': 0.15}
        rul_score = (
            temp_score * weights['temp'] +
            vib_score * weights['vib'] +
            curr_score * weights['curr'] +
            anomaly_score * weights['anomaly']
        )
        rul_score = round(max(0.0, min(100.0, rul_score)), 2)

        if rul_score >= self.low_risk_threshold:
            status = 'normal'
        elif rul_score >= self.medium_risk_threshold:
            status = 'low_risk'
        elif rul_score >= self.high_risk_threshold:
            status = 'medium_risk'
        else:
            status = 'high_risk'

        return rul_score, status, {
            'temp_avg': recent['temp_avg'],
            'vib_avg': recent['vib_avg'],
            'curr_avg': recent['curr_avg'],
            'anomalies': recent['anomaly_count'],
        }

    def analyze_all_equipments(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, equipment_code FROM equipments WHERE status = 'active'")
            equipments = [dict(r) for r in cursor.fetchall()]

        results = []
        high_risk_equipments = []

        logger.info(f"开始评估 {len(equipments)} 台设备的健康状态...")

        for eq in equipments:
            try:
                rul_score, health_status, metrics = self.calculate_rul_score(eq['id'])
                results.append({
                    'equipment_id': eq['id'],
                    'equipment_code': eq['equipment_code'],
                    'rul_score': rul_score,
                    'health_status': health_status,
                    'metrics': metrics,
                })

                self._save_health_record(eq['id'], rul_score, health_status, metrics)

                if health_status in ('high_risk', 'medium_risk'):
                    high_risk_equipments.append({
                        'equipment_id': eq['id'],
                        'equipment_code': eq['equipment_code'],
                        'rul_score': rul_score,
                        'health_status': health_status,
                    })

            except Exception as e:
                logger.error(f"分析设备 {eq.get('equipment_code')} 健康状态失败: {e}")

        logger.info(f"健康评估完成: {len(results)} 台设备, "
                     f"{len(high_risk_equipments)} 台需要关注")

        op_logger.log(
            'health_analysis', 'health_analyzer',
            f'完成 {len(results)} 台设备健康评估, {len(high_risk_equipments)} 台需关注'
        )

        return results, high_risk_equipments

    def _save_health_record(self, equipment_id, rul_score, health_status, metrics):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT MAX(completed_at) as last_maint FROM work_orders "
                               "WHERE equipment_id = ? AND status IN ('completed', 'verified')",
                               (equipment_id,))
                last_maint_row = cursor.fetchone()
                last_maint_date = last_maint_row['last_maint'] if last_maint_row else None

                cursor.execute("""
                    INSERT INTO equipment_health_records
                    (equipment_id, rul_score, health_status, temperature_avg, vibration_avg,
                     current_avg, anomalies_detected, last_maintenance_date, record_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    equipment_id, rul_score, health_status,
                    metrics.get('temp_avg'), metrics.get('vib_avg'),
                    metrics.get('curr_avg'), metrics.get('anomalies', 0),
                    last_maint_date, today_str()
                ))
        except Exception as e:
            logger.error(f"保存设备 {equipment_id} 健康记录失败: {e}")

    def get_equipment_health_history(self, equipment_id, days=30):
        with get_db_cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM equipment_health_records
                WHERE equipment_id = ? 
                AND record_date >= date('now', '-{days} days')
                ORDER BY record_date DESC
            """, (equipment_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_risk_equipments(self, min_risk='medium_risk'):
        risk_order = ['high_risk', 'medium_risk', 'low_risk', 'normal']
        min_idx = risk_order.index(min_risk)
        valid_risks = risk_order[:min_idx + 1]

        with get_db_cursor() as cursor:
            placeholders = ','.join('?' for _ in valid_risks)
            cursor.execute(f"""
                SELECT e.*, h.rul_score, h.health_status, h.record_date
                FROM equipments e
                JOIN (
                    SELECT equipment_id, MAX(record_date) as max_date
                    FROM equipment_health_records
                    GROUP BY equipment_id
                ) latest ON e.id = latest.equipment_id
                JOIN equipment_health_records h 
                    ON h.equipment_id = e.id AND h.record_date = latest.max_date
                WHERE h.health_status IN ({placeholders})
                AND e.status = 'active'
                ORDER BY h.rul_score ASC
            """, valid_risks)
            return [dict(r) for r in cursor.fetchall()]
