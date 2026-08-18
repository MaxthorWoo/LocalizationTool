# -*- coding: utf-8 -*-
"""临时验证：生产环境最终术语命中。"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from localization.services import term_service

# 场景1：繁体原文 vs 简体术语（测试 01 工程）
text = "《神器傳説》團隊 的 仙界盲盒 開啟"
terms, _ = term_service.terms_for_prompt(0, target_lang="en", source_lang="zh-TW")
hits = term_service.match_terms(text, terms)
print("场景1 命中:", hits)

# 场景2：简体原文 vs 繁体术语（反向）
text2 = "神器传说 开启 测试"
hits2 = term_service.match_terms(text2, terms)
print("场景2 命中:", hits2)

# 场景3：纯英文（无 zhconv 影响）
text3 = "Hello World testing system"
hits3 = term_service.match_terms(text3, terms)
print("场景3 命中:", hits3)
