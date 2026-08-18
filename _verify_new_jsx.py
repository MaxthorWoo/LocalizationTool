# -*- coding: utf-8 -*-
"""临时验证：新编译产物中的样式。"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = r"e:/WebApp/LocalizationTool/.web/app_components/localization/pages"
p = os.path.join(root, "project.jsx")
with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
    c = fh.read()

for kw in ["fieldSizing", "tableLayout", "textAlign", "maxHeight", "overflowY", "wordBreak", "flexBasis"]:
    print(f"{kw}: {kw in c}")

# 检查 tableLayout 是否作为 Table.Root 的 prop
for m in re.finditer(r"RadixThemesTable\.Root", c):
    i = m.start()
    seg = c[i:i + 400].replace("\n", " ")
    print("\n=== Table.Root ===")
    print(seg[:380])
    break
else:
    # 找所有 RadixThemesTable 标签
    tags = set(re.findall(r"RadixThemesTable\.[A-Za-z]+", c))
    print("\nTable tags:", sorted(tags))
    # 检查 Row 中 textAlign
    hits = [m.start() for m in re.finditer(r"RadixThemesTable\.Row", c)]
    print("Row count:", len(hits))
    if hits:
        seg = c[hits[0]:hits[0] + 1500].replace("\n", " ")
        print("=== First Row area ===")
        print(seg[:1400])
