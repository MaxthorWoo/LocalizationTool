import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from localization.services import term_service
from localization.services.translation_service import build_messages, _filter_longest_hits
from localization.services import prompt_service

# 纯文本工程 source_lang? 查 project 表
import sqlite3

con = sqlite3.connect(r"e:\WebApp\LocalizationTool\localization.db")
cur = con.cursor()
cur.execute("SELECT source_lang, name FROM project WHERE id=2")
print("project:", cur.fetchone())
con.close()

terms, ctx = term_service.terms_for_prompt(1, target_lang="ko", source_lang="zh-CN")
print("total terms:", len(terms))
hits = term_service.match_terms("神器传说", terms)
print("hits:", hits)
hits_f = _filter_longest_hits(hits)
print("filtered hits:", hits_f)
term_by_source = {t.source_term: t for t in terms if t.source_term}
hit_terms = [term_by_source[w] for w in hits_f if w in term_by_source]
for t in hit_terms:
    print("hit term:", t.source_term, "->", t.get_translations())
term_context = term_service.build_term_context(hit_terms, "ko")
print("\n=== term_context (ko) ===")
print(term_context)

term_context_en = term_service.build_term_context(hit_terms, "en")
print("\n=== term_context (en) ===")
print(term_context_en)

# 渲染韩语模板的最终消息
tpl = prompt_service.get_template(2)
msgs = tpl.get_messages()
print("\n=== 韩语模板最终 messages（末3条）===")
rendered = build_messages(
    msgs,
    source_text="神器传说",
    source_lang="zh-CN",
    target_lang="ko",
    term_context=term_context,
)
for i, m in enumerate(rendered):
    print(f"\n--- {i}. [{m['role']}] ---")
    print(m["content"])
