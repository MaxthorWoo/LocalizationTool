# -*- coding: utf-8 -*-
"""临时验证：统一转简体后的匹配。"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from zhconv import convert

text = "《神器傳説》團隊"
term = "神器传说"
text_cn = convert(text, "zh-cn")
term_cn = convert(term, "zh-cn")
print("原文转简:", text_cn)
print("术语转简:", term_cn)
print("简体命中:", term_cn in text_cn)

# 再验证异体字场景：原文用「説」异体
print("直接繁中比较:", term_cn in text)
# 验证长文本
t2 = "神器傳説 測試 世界"
t2_cn = convert(t2, "zh-cn")
print("长文本转简:", t2_cn)
