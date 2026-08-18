# -*- coding: utf-8 -*-
"""临时验证：繁简归一化后的完整术语命中链路。"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from localization.services import term_service

# 模拟真实场景：工程源语言 zh-TW，原文繁体，术语库简体
text = "《神器傳説》團隊 的 仙界盲盒 開啟"
terms, ctx = term_service.terms_for_prompt(0, target_lang="en", source_lang="zh-TW")
print("术语总数:", len(terms))

hits = term_service.match_terms(text, terms)
print("命中词:", hits)

# 从翻译服务复制最长匹配过滤逻辑验证
from localization.services.translation_service import _filter_longest_hits

hit_words = _filter_longest_hits(hits)
print("过滤后:", hit_words)

term_by_source = {t.source_term: t for t in terms if t.source_term}
hit_terms = [term_by_source[w] for w in hit_words if w in term_by_source]
context = term_service.build_term_context(hit_terms, "en")
print("注入上下文:\n", context[:400])
