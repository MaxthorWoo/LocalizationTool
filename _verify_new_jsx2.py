# -*- coding: utf-8 -*-
"""临时验证：查找表格根与表头。"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

p = r"e:/WebApp/LocalizationTool/.web/app_components/localization/pages/project.jsx"
with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
    c = fh.read()

# 查找 'table' 相关
for m in re.finditer(r"table", c, re.IGNORECASE):
    i = m.start()
    seg = c[max(0, i - 60):i + 80].replace("\n", " ")
    if "Root" in seg or "Header" in seg or "layout" in seg or "ColumnHeader" in seg:
        print(">>>", seg[:160])
        print()
