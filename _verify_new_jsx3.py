# -*- coding: utf-8 -*-
"""临时验证：扫描所有 project 编译文件。"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = r"e:/WebApp/LocalizationTool/.web"
targets = [
    "tableLayout",
    "table_layout",
    "textAlign",
    "text_align",
    "Table.Header",
    "Table.Root",
    "Table.Body",
]
found_files = set()
for dp, dn, fn in os.walk(root):
    if "node_modules" in dp:
        continue
    for f in fn:
        if not (f.endswith(".jsx") or f.endswith(".js")):
            continue
        p = os.path.join(dp, f)
        try:
            with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
                c = fh.read()
        except Exception:
            continue
        for t in targets:
            if t in c:
                found_files.add((os.path.relpath(p, root), t))
print("found:")
for rel, t in sorted(found_files):
    print(" ", rel, "->", t)
