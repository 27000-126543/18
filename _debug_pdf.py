import sys, traceback
sys.path.insert(0, '/Users/mac/Desktop/6.5项目/18')

from modules.daily_report import DailyReportGenerator
from utils.helpers import today_str

gen = DailyReportGenerator()
stats = gen._collect_daily_stats(today_str())
print("Stats collected:", list(stats.keys())[:5], "...")

try:
    ok = gen.export_pdf(stats, '/Users/mac/Desktop/6.5项目/18/_debug_test.pdf')
    print("export_pdf returned:", ok)
except Exception as e:
    print("EXCEPTION:")
    traceback.print_exc()
