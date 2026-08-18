# -*- coding: utf-8 -*-
"""临时验证：添加语言后条目序列化逻辑。"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from localization.state import EntryRow
from localization import models as m


def serialize_entry(e, target_langs, lang_code_to_display):
    """模拟 _serialize_entry 的 cells 生成逻辑。"""
    translations = e.get_translations()
    cells = [
        {"lang": lang, "text": translations.get(lang, "")}
        for lang in target_langs
    ]
    return cells


# 模拟一个条目：已有 zh-TW 译文，无 en 译文
class FakeEntry:
    def __init__(self, source_text, translations):
        self.source_text = source_text
        self._translations = translations
        self.key_text = ""
        self.status = "draft"
        self.id = 1

    def get_translations(self):
        return dict(self._translations)

    def get_term_hits(self):
        return []


e = FakeEntry("神器傳説", {"zh-TW": "神器傳說"})

# 场景1：只有 zh-TW（添加 en 前）
cells_before = serialize_entry(e, ["zh-TW"], {})
print("添加前 cells:", cells_before)

# 场景2：添加 en 后
cells_after = serialize_entry(e, ["zh-TW", "en"], {})
print("添加后 cells:", cells_after)
assert cells_after == [
    {"lang": "zh-TW", "text": "神器傳說"},
    {"lang": "en", "text": ""},
], "cells 未正确生成新列"
print("PASS: 新增语言后输入框列正确生成（空输入框）")
