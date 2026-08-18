import sys

sys.stdout.reconfigure(encoding="utf-8")

f = open(r"e:\WebApp\LocalizationTool\.web\app_components\localization\pages\project.jsx", "r", encoding="utf-8")
s = f.read()
import re

for m in list(re.finditer(r"progress_pct", s)):
    print("---")
    print(s[max(0, m.start() - 150): m.start() + 100])
