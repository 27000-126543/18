from core.database import get_db_cursor


def init_database():
    with get_db_cursor(commit=True) as cursor:
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS equipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                location TEXT NOT NULL,
                manufacturer TEXT,
                model TEXT,
                install_date TEXT,
                status TEXT DEFAULT 'active',
                initial_cost REAL DEFAULT 0,
                expected_lifespan_days INTEGER DEFAULT 3650,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS equipment_health_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                rul_score REAL NOT NULL,
                health_status TEXT NOT NULL,
                temperature_avg REAL,
                vibration_avg REAL,
                current_avg REAL,
                anomalies_detected INTEGER DEFAULT 0,
                last_maintenance_date TEXT,
                record_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipments(id)
            );

            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                temperature REAL,
                vibration REAL,
                current REAL,
                pressure REAL,
                rpm REAL,
                collection_time TEXT NOT NULL,
                is_anomaly INTEGER DEFAULT 0,
                FOREIGN KEY (equipment_id) REFERENCES equipments(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sensor_data_equipment_time 
                ON sensor_data(equipment_id, collection_time);
            CREATE INDEX IF NOT EXISTS idx_sensor_data_time 
                ON sensor_data(collection_time);

            CREATE TABLE IF NOT EXISTS engineers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE NOT NULL,
                specialty TEXT NOT NULL,
                location TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                workload INTEGER DEFAULT 0,
                rating REAL DEFAULT 5.0,
                status TEXT DEFAULT 'available',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS work_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                equipment_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                engineer_id INTEGER,
                assigned_at TEXT,
                deadline TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                verified_at TEXT,
                escalation_level INTEGER DEFAULT 0,
                maintenance_cost REAL DEFAULT 0,
                parts_used TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipments(id),
                FOREIGN KEY (engineer_id) REFERENCES engineers(id)
            );

            CREATE TABLE IF NOT EXISTS work_order_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_order_id INTEGER NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                changed_by TEXT,
                changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                note TEXT,
                FOREIGN KEY (work_order_id) REFERENCES work_orders(id)
            );

            CREATE TABLE IF NOT EXISTS maintenance_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_order_id INTEGER NOT NULL,
                equipment_id INTEGER NOT NULL,
                pre_temperature_avg REAL,
                post_temperature_avg REAL,
                pre_vibration_avg REAL,
                post_vibration_avg REAL,
                pre_current_avg REAL,
                post_current_avg REAL,
                improvement_rate REAL,
                is_passed INTEGER DEFAULT 0,
                verifier TEXT,
                verification_date TEXT,
                report TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (work_order_id) REFERENCES work_orders(id),
                FOREIGN KEY (equipment_id) REFERENCES equipments(id)
            );

            CREATE TABLE IF NOT EXISTS spare_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                unit TEXT NOT NULL,
                unit_price REAL NOT NULL,
                safety_stock INTEGER DEFAULT 0,
                current_stock INTEGER DEFAULT 0,
                lead_time_days INTEGER DEFAULT 7,
                applicable_equipment_types TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                reference_no TEXT,
                operator TEXT,
                transaction_date TEXT DEFAULT CURRENT_TIMESTAMP,
                note TEXT,
                FOREIGN KEY (part_id) REFERENCES spare_parts(id)
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                contact_person TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                quality_score REAL DEFAULT 80,
                delivery_score REAL DEFAULT 80,
                price_score REAL DEFAULT 80,
                overall_score REAL DEFAULT 80,
                total_orders INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS supplier_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                part_id INTEGER NOT NULL,
                price REAL NOT NULL,
                lead_time_days INTEGER DEFAULT 7,
                is_preferred INTEGER DEFAULT 0,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (part_id) REFERENCES spare_parts(id),
                UNIQUE(supplier_id, part_id)
            );

            CREATE TABLE IF NOT EXISTS purchase_requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                req_no TEXT UNIQUE NOT NULL,
                part_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                estimated_cost REAL,
                reason TEXT,
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                budget_amount REAL,
                approval_status TEXT DEFAULT 'pending',
                approver TEXT,
                approved_at TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (part_id) REFERENCES spare_parts(id)
            );

            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                requisition_id INTEGER,
                part_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                expected_delivery TEXT,
                actual_delivery TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (requisition_id) REFERENCES purchase_requisitions(id),
                FOREIGN KEY (part_id) REFERENCES spare_parts(id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                level TEXT NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                content TEXT,
                related_type TEXT,
                related_id INTEGER,
                is_read INTEGER DEFAULT 0,
                is_sent INTEGER DEFAULT 0,
                sent_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT UNIQUE NOT NULL,
                total_equipments INTEGER,
                active_equipments INTEGER,
                fault_count INTEGER,
                fault_rate REAL,
                avg_repair_time_hours REAL,
                total_maintenance_cost REAL,
                high_risk_equipments INTEGER,
                pending_work_orders INTEGER,
                completed_work_orders INTEGER,
                low_stock_items INTEGER,
                report_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS monthly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_month TEXT UNIQUE NOT NULL,
                total_equipment_cost REAL,
                total_maintenance_cost REAL,
                total_parts_cost REAL,
                total_lifecycle_cost REAL,
                avg_failure_rate REAL,
                avg_mtbf_hours REAL,
                avg_mttr_hours REAL,
                equipment_utilization REAL,
                report_path_pdf TEXT,
                report_path_excel TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS equipment_scraps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER UNIQUE NOT NULL,
                scrap_date TEXT NOT NULL,
                scrap_reason TEXT,
                residual_value REAL DEFAULT 0,
                related_parts_disposed TEXT,
                operator TEXT,
                approval_status TEXT DEFAULT 'pending',
                approver TEXT,
                approved_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipments(id)
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                module TEXT NOT NULL,
                equipment_code TEXT,
                operator TEXT,
                description TEXT,
                ip_address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_logs_equipment 
                ON operation_logs(equipment_code);
            CREATE INDEX IF NOT EXISTS idx_logs_type_time 
                ON operation_logs(operation_type, created_at);
            CREATE INDEX IF NOT EXISTS idx_logs_time 
                ON operation_logs(created_at);
        """)
