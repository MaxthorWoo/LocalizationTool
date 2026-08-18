# -*- coding: utf-8 -*-
"""临时验证：组件顶层 prop 与 style 的区别。"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import reflex as rx

# 顶层 prop
b1 = rx.box("test", text_align="center")
# style 内
b2 = rx.box("test", style={"text_align": "center"})

print("top-level prop:", b1.render())
print()
print("style prop:", b2.render())
