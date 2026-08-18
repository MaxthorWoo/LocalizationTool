# -*- coding: utf-8 -*-
"""临时检查：编译产物中的表格样式。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

p = r"e:/WebApp/LocalizationTool/.web/app_components/localization/pages/project.jsx"
with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
    c = fh.read()

# 查找 Table.Root
for m in re.finditer(r"RadixThemesTable\.Root", c):
    i = m.start()
    seg = c[i:i + 300].replace("\n", " ")
    print("Table.Root:", seg[:260])
    print()
    break

# 查找 Table.ColumnHeaderCell 上下文
hits = [m.start() for m in re.finditer(r"RadixThemesTable\.ColumnHeaderCell", c)]
print("ColumnHeaderCell count:", len(hits))
for i in hits[:3]:
    seg = c[i:i + 200].replace("\n", " ")
    print("  >", seg[:180])
    print()

# 查找 tableLayout
print("tableLayout present:", "tableLayout" in c)
# 查找 textAlign
print("textAlign present:", "textAlign" in c)
