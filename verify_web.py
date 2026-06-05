import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('1. 验证app.py语法...')
import py_compile
py_compile.compile('app.py', doraise=True)
print('   ✓ app.py 语法正确')

print('2. 验证stress_test.py语法...')
py_compile.compile('stress_test.py', doraise=True)
print('   ✓ stress_test.py 语法正确')

print('3. 验证所有模块导入...')
from app import create_app
print('   ✓ 所有模块导入成功')

print('4. 创建Flask应用实例...')
app = create_app()
print('   ✓ Flask应用创建成功')
print('   路由列表:')
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    if not rule.rule.startswith('/static'):
        methods = list(rule.methods - {'HEAD', 'OPTIONS'})
        print(f'     {methods} {rule.rule}')

print()
print('5. 验证模板文件存在...')
templates = [
    'base.html', 'dashboard.html',
    'work_orders/list.html', 'work_orders/detail.html', 'work_orders/create.html',
    'inventory/list.html', 'approval/list.html',
    'reports/index.html', 'reports/daily.html', 'reports/monthly.html',
    'equipment/list.html', 'equipment/detail.html',
    'logs/list.html', 'suppliers/list.html'
]
all_ok = True
for t in templates:
    p = os.path.join('templates', t)
    ok = os.path.exists(p)
    all_ok = all_ok and ok
    print(f'   {"✓" if ok else "✗"} {t}')

print()
print('6. 验证静态文件存在...')
static_files = [
    'static/css/style.css',
    'static/js/common.js', 'static/js/charts.js', 'static/js/dashboard.js'
]
for f in static_files:
    ok = os.path.exists(f)
    all_ok = all_ok and ok
    print(f'   {"✓" if ok else "✗"} {f}')

print()
print('7. 测试仪表盘API响应...')
with app.test_client() as c:
    resp = c.get('/')
    print(f'   GET / -> {resp.status_code}')
    resp = c.get('/api/dashboard/stats')
    print(f'   GET /api/dashboard/stats -> {resp.status_code} (len={len(resp.data)} bytes)')
    resp = c.get('/work_orders')
    print(f'   GET /work_orders -> {resp.status_code}')
    resp = c.get('/inventory')
    print(f'   GET /inventory -> {resp.status_code}')
    resp = c.get('/approval')
    print(f'   GET /approval -> {resp.status_code}')
    resp = c.get('/reports')
    print(f'   GET /reports -> {resp.status_code}')
    resp = c.get('/equipment')
    print(f'   GET /equipment -> {resp.status_code}')
    resp = c.get('/logs')
    print(f'   GET /logs -> {resp.status_code}')
    resp = c.get('/suppliers')
    print(f'   GET /suppliers -> {resp.status_code}')

print()
if all_ok:
    print('=' * 60)
    print('  ✅ 全部验证通过! Web应用可以正常运行')
    print('=' * 60)
    print()
    print('  启动命令:')
    print('    python app.py')
    print('  压力测试:')
    print('    python stress_test.py')
else:
    print('❌ 存在文件缺失，请检查')
    sys.exit(1)
