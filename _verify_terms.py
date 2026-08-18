"""真实验证：术语"神器传说"在 en/ko 下是否被严格照用（只调 API 不写库）。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from localization.services import file_service, term_service, prompt_service
from localization.services.translation_service import translate_one, _filter_longest_hits
from localization.models import Entry
from localization.translators import create_translator

for lang, api_id, tpl_id in (("en", 4, 1), ("ko", 3, 2)):
    api = file_service.get_api_config(api_id)
    tpl = prompt_service.get_template(tpl_id)
    msgs = tpl.get_messages()
    terms, _ = term_service.terms_for_prompt(1, target_lang=lang, source_lang="zh-CN")
    hit_words = _filter_longest_hits(term_service.match_terms("神器传说", terms))
    term_by_source = {t.source_term: t for t in terms if t.source_term}
    hit_terms = [term_by_source[w] for w in hit_words if w in term_by_source]
    term_context = term_service.build_term_context(hit_terms, lang)
    print(f"\n=== {lang} ===")
    print("hit terms:", [(t.source_term, t.get_translations().get(lang, "")) for t in hit_terms])
    print("term_context:", term_context.replace("\n", " | "))

    translator = create_translator(api.engine_name, api)
    entry = Entry()
    entry.source_text = "神器传说"
    entry.key_text = ""
    out = translate_one(
        translator,
        msgs,
        entry,
        "zh-CN",
        lang,
        term_context,
        user_instruction="",
    )
    print(f"RAW OUTPUT: {out!r}")
