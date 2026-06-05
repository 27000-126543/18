import urllib.request
import os, sys

BASE = "http://127.0.0.1:5001"

print("=== 核心路由测试 ===")
paths = [
    ("/", "仪表盘"),
    ("/settings/email", "邮件配置页"),
    ("/approval", "审批中心"),
    ("/reports", "报表中心"),
    ("/inventory", "库存管理"),
    ("/work_orders", "工单管理"),
    ("/api/dashboard/stats", "仪表盘API"),
    ("/api/email/test", "邮件测试API"),
]
ok = True
for p, label in paths:
    try:
        req = urllib.request.urlopen(BASE + p, timeout=15)
        print(f"  {req.status:3d} - {label}")
        if req.status != 200:
            ok = False
    except Exception as e:
        print(f"  ERR - {label}: {e}")
        ok = False

print()
print("=== 导出功能测试 ===")
for name, url in [
    ("日报Excel", "/reports/daily/export/excel"),
    ("日报PDF",   "/reports/daily/export/pdf"),
    ("月报Excel", "/reports/monthly/export/excel"),
    ("月报PDF",   "/reports/monthly/export/pdf"),
]:
    try:
        req = urllib.request.urlopen(BASE + url, timeout=45)
        data = req.read()
        print(f"  {req.status:3d} - {name:10s} size={len(data):>8,} bytes")
        if req.status != 200 or len(data) < 500:
            ok = False
    except Exception as e:
        print(f"  ERR - {name}: {e}")
        ok = False

print()
print("=== 邮件API返回 ===")
try:
    req = urllib.request.urlopen(BASE + "/api/email/test", timeout=15)
    print("  " + req.read().decode('utf-8'))
except Exception as e:
    print(f"  ERR: {e}")

print()
print("=" * 50)
if ok:
    print("所有测试通过 ✓")
else:
    print("存在失败项 ✗")
    sys.exit(1)
