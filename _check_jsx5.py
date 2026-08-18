# -*- coding: utf-8 -*-
"""临时检查：查找表格相关所有标签。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

p = r"e:/WebApp/LocalizationTool/.web/app_components/localization/pages/project.jsx"
with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
    c = fh.read()

# 找 Table.Row 上下文，看看被什么包裹
for m in re.finditer(r"RadixThemesTable\.Row", c):
    i = m.start()
    print("=== Row area ===")
    print(c[max(0, i - 800):i + 200].replace("\n", " ")[:1000])
    print()
    break
