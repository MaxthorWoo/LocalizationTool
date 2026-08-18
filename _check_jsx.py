# -*- coding: utf-8 -*-
"""临时检查：编译产物中的样式。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

p = r"e:/WebApp/LocalizationTool/.web/app_components/localization/pages/project.jsx"
with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
    c = fh.read()

for kw in ["fieldSizing", "tableLayout", "table_layout", "textAlign", "text_align", "flex", "maxHeight"]:
    idxs = [m.start() for m in re.finditer(re.escape(kw), c)]
    if idxs:
        print("===", kw, "count:", len(idxs))
        i = idxs[0]
        print(c[max(0, i - 100):i + 150].replace("\n", " "))
        print()
