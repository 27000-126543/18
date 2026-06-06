import sys, traceback
sys.path.insert(0, '/Users/mac/Desktop/6.5项目/18')

from app import create_app

app = create_app()
client = app.test_client()

print("=== Test daily PDF ===")
try:
    resp = client.get('/reports/daily/export/pdf')
    print(f"Status: {resp.status_code}")
    print(f"Content-Length: {len(resp.data)}")
    if resp.status_code != 200:
        print(f"Response body: {resp.data.decode('utf-8', errors='replace')}")
except Exception as e:
    traceback.print_exc()

print()
print("=== Test monthly PDF ===")
try:
    resp = client.get('/reports/monthly/export/pdf')
    print(f"Status: {resp.status_code}")
    print(f"Content-Length: {len(resp.data)}")
    if resp.status_code != 200:
        print(f"Response body: {resp.data.decode('utf-8', errors='replace')}")
except Exception as e:
    traceback.print_exc()
