import sys
sys.path.insert(0, '/Users/mac/Desktop/6.5项目/18')
import re
import os
os.chdir('/Users/mac/Desktop/6.5项目/18')

from modules.daily_report import DailyReportGenerator
from modules.monthly_report import MonthlyReportGenerator
from utils.helpers import today_str, month_str

dr = DailyReportGenerator()
stats_d = dr._collect_daily_stats(today_str())
dr.export_pdf(stats_d, '_debug_daily.pdf')

mr = MonthlyReportGenerator()
stats_m = mr._collect_monthly_stats(month_str())
mr.export_pdf(stats_m, '_debug_monthly.pdf')

def check_pdf_fonts(path):
    with open(path, 'rb') as f:
        data = f.read()
    font_names = re.findall(rb'/BaseFont\s+/([^/\s\]]+)', data)
    uniq = sorted(set(font_names))
    decoded = [f.decode('latin-1', errors='replace') for f in uniq]
    print(f"\n{path} ({len(data):,} bytes):")
    print(f"  嵌入字体: {decoded}")
    has_cjk = any(('PingFang' in f or 'STHeiti' in f or 'SimSun' in f
                   or 'DRF_' in f or 'MRF_' in f or 'Hiragino' in f
                   or 'Songti' in f) for f in decoded)
    print(f"  包含中文字体: {'YES ✓' if has_cjk else 'NO ✗'}")
    return has_cjk

ok_d = check_pdf_fonts('_debug_daily.pdf')
ok_m = check_pdf_fonts('_debug_monthly.pdf')

print()
if ok_d and ok_m:
    print("SUCCESS: 日报和月报PDF都已嵌入中文字体，中文不会显示为方框")
else:
    print("FAIL: 部分PDF未嵌入中文字体")
    sys.exit(1)
