# 制造业预测性维护Web系统 - 技术架构文档

## 1. 整体架构

### 1.1 架构图

```
┌───────────────────────────────────────────────────────────────┐
│                        用户浏览器                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ 仪表盘   │  │ 工单管理 │  │ 库存管理 │  │ 报表/审批中心 │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │              │              │                │          │
│  ┌────┴──────────────┴──────────────┴────────────────┴───────┐  │
│  │            ECharts 5 图表引擎 + 原生JS交互层               │  │
│  └──────────────────────────┬────────────────────────────────┘  │
└─────────────────────────────┼──────────────────────────────────┘
                              │ HTTPS / JSON API
┌─────────────────────────────┴──────────────────────────────────┐
│                    Flask 3.0  Web应用层                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐ │
│  │  路由层     │ │  模板渲染  │ │  API层      │ │  静态资源    │ │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └──────┬──────┘ │
│        │              │              │                │        │
│  ┌─────┴──────────────┴──────────────┴────────────────┴──────┐ │
│  │                    业务逻辑模块 (14个)                      │ │
│  │ 传感器采集 │ 健康评估 │ 工单调度 │ 库存优化 │ 邮件通知 ... │ │
│  └──────────────────────────┬────────────────────────────────┘ │
└─────────────────────────────┼──────────────────────────────────┘
                              │
┌─────────────────────────────┴──────────────────────────────────┐
│                    数据持久化层                                  │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │  SQLite3 (WAL)  │  │ 文件系统      │  │ 日志/报表文件   │   │
│  │  19张业务表     │  │ templates/    │  │  reports/       │   │
│  │  +6个索引       │  │ static/       │  │  logs/          │   │
│  └─────────────────┘  └──────────────┘  └─────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 目录结构

```
18/
├── app.py                    # Flask应用入口
├── main.py                   # 独立调度器入口（原main.py）
├── cli.py                    # 命令行工具
├── quick_verify.py           # 快速验证脚本
├── stress_test.py            # 高并发压力测试脚本
├── requirements.txt          # Python依赖
├── config/
│   ├── __init__.py
│   └── settings.py           # 系统配置（含邮件SMTP配置）
├── core/
│   ├── database.py           # 数据库连接层
│   ├── logger.py             # 日志系统
│   └── email_service.py      # 邮件服务（SMTP真实发送）
├── models/
│   └── schema.py             # 数据库表结构
├── modules/                  # 14个业务逻辑模块
├── utils/
│   ├── helpers.py            # 工具函数
│   └── dependency_installer.py  # 自动依赖安装器
├── templates/                # Jinja2模板
│   ├── base.html             # 基础模板（侧边栏+顶部导航）
│   ├── dashboard.html        # 仪表盘
│   ├── work_orders/          # 工单管理页面
│   ├── inventory/            # 库存管理页面
│   ├── approval/             # 审批中心页面
│   ├── reports/              # 报表中心页面
│   ├── equipment/            # 设备管理页面
│   └── logs/                 # 日志查询页面
├── static/
│   ├── css/
│   │   └── style.css         # 工业科技风样式
│   └── js/
│       ├── dashboard.js      # 仪表盘图表与交互
│       ├── charts.js         # 通用图表封装
│       └── common.js         # 通用工具函数
├── data/                     # 数据库文件
├── reports/                  # 报表输出
└── logs/                     # 系统日志
```

---

## 2. 核心技术选型详解

### 2.1 后端框架：Flask 3.0

| 特性 | 说明 |
|------|------|
| 轻量 | 核心库小，启动快，适合快速迭代 |
| Jinja2模板 | 服务端渲染，SEO友好，开发效率高 |
| 蓝图(Blueprints) | 可将路由模块化拆分（dashboard、work_orders、inventory等） |
| Flask-CORS | 预留跨域支持，便于后续前后端分离 |

### 2.2 前端技术栈

| 技术 | 用途 | 加载方式 |
|------|------|---------|
| ECharts 5.4 | 仪表盘/图表可视化 | CDN引入 (`https://cdn.jsdelivr.net/npm/echarts@5.4.3`) |
| 原生HTML5/CSS3 | 页面结构与样式 | 本地static文件 |
| 原生JavaScript ES6+ | 交互逻辑、AJAX请求 | 本地static文件 |
| CSS Grid + Flexbox | 响应式布局 | 内联实现 |

### 2.3 数据库：SQLite3 (WAL模式)

- **WAL模式**：Write-Ahead Logging，读写不阻塞，支持高并发
- **关键配置**：`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA cache_size=-64000;`
- **索引优化**：sensor_data(equipment_id, collection_time)、operation_logs(time, equipment_code)等6个复合索引
- **可扩展性**：数据库访问全部通过`core/database.py`封装，后续可平滑切换PostgreSQL仅需修改此文件

### 2.4 邮件服务：Python smtplib + email

```python
# 配置项 (config/settings.py新增)
EMAIL_CONFIG = {
    'smtp_server': 'smtp.exmail.qq.com',
    'smtp_port': 465,
    'use_ssl': True,
    'username': 'noreply@factory.com',
    'password': 'your_app_password',
    'sender_name': '预测性维护系统',
    'max_retries': 3,
    'retry_interval': 5,  # 秒
}
```

- 支持SSL/TLS加密发送
- 失败自动重试3次，指数退避
- HTML富文本邮件模板（工单升级、库存预警、审批提醒各有独立样式）

### 2.5 导出与自动依赖安装

```python
# utils/dependency_installer.py
def ensure_dependency(package_name, import_name=None):
    """确保依赖已安装，未安装则自动pip install"""
    try:
        __import__(import_name or package_name)
        return True
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package_name, '-q'])
        __import__(import_name or package_name)
        return True
```

- Excel导出：`openpyxl` - 缺失时自动安装
- PDF导出：`reportlab` - 缺失时自动安装
- 安装过程对用户透明，带加载提示

---

## 3. 关键模块设计

### 3.1 Flask路由设计

| URL路径 | HTTP方法 | 蓝图 | 功能 |
|---------|---------|------|------|
| `/` | GET | dashboard | 仪表盘首页 |
| `/api/dashboard/stats` | GET | dashboard | JSON仪表盘数据接口 |
| `/api/sensor/realtime/<equipment_id>` | GET | dashboard | 实时传感器数据JSON |
| `/work_orders` | GET | work_orders | 工单列表 |
| `/work_orders/<id>` | GET/POST | work_orders | 工单详情/更新状态 |
| `/work_orders/create` | GET/POST | work_orders | 创建工单 |
| `/inventory` | GET | inventory | 备件列表 |
| `/inventory/transaction` | POST | inventory | 出入库操作 |
| `/approval` | GET | approval | 审批工作台 |
| `/approval/<id>/approve` | POST | approval | 通过审批 |
| `/approval/<id>/reject` | POST | approval | 驳回审批 |
| `/reports/daily` | GET | reports | 日报展示 |
| `/reports/daily/export/<format>` | GET | reports | 日报导出（excel/pdf） |
| `/reports/monthly` | GET | reports | 月度报告 |
| `/equipment` | GET | equipment | 设备列表 |
| `/equipment/<id>` | GET | equipment | 设备详情 |
| `/equipment/scrap` | POST | equipment | 设备报废 |
| `/logs` | GET | logs | 操作日志查询 |
| `/logs/export` | GET | logs | 日志批量导出 |

### 3.2 仪表盘数据流

```
浏览器请求 / 
  → Flask渲染 base.html + dashboard.html
  → 页面加载后AJAX请求 /api/dashboard/stats
    → 健康评估模块统计RUL分布
    → 工单模块查询各状态数量
    → 库存模块查询低库存备件
    → 传感器模块查询最新异常数据
  → 返回JSON
  → ECharts渲染环形图、柱状图、折线图
  → setInterval每30秒刷新一次实时数据
```

### 3.3 邮件通知流程

```python
触发事件（工单超时/库存低/超预算申请）
  → NotificationManager.create_notification(...)
  → 写notifications表
  → EmailService.send_email(to, subject, html_body)
    → 检查SMTP配置
    → 渲染HTML邮件模板
    → 循环重试最多3次（间隔5s）
    → 更新notification.is_sent状态
    → 失败写入error.log
```

---

## 4. 高并发压力测试方案

### 4.1 压测工具：Python asyncio + aiohttp

**测试场景**：
1. **数据采集压测**：模拟N台设备并发发送传感器数据，验证数据库写入TPS
2. **API查询压测**：并发请求仪表盘接口，验证读性能
3. **混合场景压测**：70%读 + 30%写，模拟真实生产负载

**关键指标**：
- QPS (Queries Per Second)
- P50/P95/P99响应时间
- 错误率（目标<0.1%）
- 数据库锁等待时间
- 内存/CPU占用

### 4.2 压测分级

| 级别 | 设备数 | 日数据点 | 持续时间 |
|------|--------|---------|---------|
| L1 基础 | 500 | 5万 | 10分钟 |
| L2 标准 | 2000 | 25万 | 30分钟 |
| L3 极限 | 5000 | 50万 | 60分钟 |

---

## 5. 性能优化策略

1. **数据库**：WAL模式 + 批量写入(executemany) + 预编译SQL
2. **数据采集**：ThreadPoolExecutor 500并发 → 批次1000条批量插入
3. **前端**：ECharts懒加载 + 数据增量更新 + CSS硬件加速
4. **缓存**：设备基线数据内存缓存（日粒度过期）
5. **静态资源**：CSS/JS最小化，CDN加载ECharts

---

## 6. 安全设计

1. **SQL注入防护**：全部使用参数化查询，禁止字符串拼接SQL
2. **XSS防护**：Jinja2模板自动转义，用户输入过滤
3. **CSRF防护**：Flask-WTF CSRF Token
4. **操作审计**：所有写操作写operation_logs表（操作人/IP/时间/详情）
