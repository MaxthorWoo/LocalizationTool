# -*- coding: utf-8 -*-
"""临时检查：所有表格相关标签。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

p = r"e:/WebApp/LocalizationTool/.web/app_components/localization/pages/project.jsx"
with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
    c = fh.read()

tags = set(re.findall(r"RadixThemesTable\.[A-Za-z]+", c))
print("Table tags:", sorted(tags))

# 找 Table.Root 区域
for m in re.finditer(r"RadixThemesTable\.Root", c):
    i = m.start()
    print("\n=== Table.Root area ===")
    print(c[i:i + 2500].replace("\n", " ")[:2400])
    break
