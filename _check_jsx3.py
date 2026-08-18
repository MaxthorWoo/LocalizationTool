# -*- coding: utf-8 -*-
"""临时检查：表格完整结构。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

p = r"e:/WebApp/LocalizationTool/.web/app_components/localization/pages/project.jsx"
with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
    c = fh.read()

# 查找 TableHeader 区域
idx = c.find("RadixThemesTable.Header")
if idx == -1:
    print("no Table.Header found")
else:
    seg = c[idx:idx + 1200].replace("\n", " ")
    print("HEADER AREA:", seg[:1100])
    print()

# 查找 table_layout 相关
for kw in ["table_layout", "tableLayout", "text_align", "textAlign"]:
    print(kw, ":", kw in c)
