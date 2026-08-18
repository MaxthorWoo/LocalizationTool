import sys
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect(r"e:\WebApp\LocalizationTool\localization.db")
cur = con.cursor()

# 英文模板 id=1：强调术语最高优先级
cur.execute("SELECT messages FROM prompttemplate WHERE id=1")
raw = cur.fetchone()[0]
import json

msgs = json.loads(raw)
for m in msgs:
    if m["role"] == "user" and "术语库参考" in m["content"]:
        m["content"] = (
            "术语库参考：{term_context}，需要严格遵循术语的翻译，如遇到对应词汇，不得乱翻译，"
            "如术语库为空，则正常翻译。\n\n"
            "注意：术语库中指定的译法具有最高优先级，必须原样使用，"
            "禁止增删改任何字词（包括冠词、时态、单复数等变化）。\n\n"
            "遵照术语库的基准，将 {source_text} 翻译成 {target_lang_name}，"
            "不要保留源语言的任何文本词汇，全部字词都要翻译成目标语言文本，"
            "最后只需要输出翻译的内容，无需输出推理、思考等其他内容。\n\n"
            "注意：请保留原文的换行与段落结构，禁止使用 ** ** 或 * * 等任何 Markdown 加粗/斜体标记，"
            "只输出纯文本翻译。"
        )
        print("patched template 1")

cur.execute(
    "UPDATE prompttemplate SET messages=? WHERE id=1",
    (json.dumps(msgs, ensure_ascii=False),),
)
con.commit()
print("template 1 updated")

# 检查默认内置模板（若用户未配置模板时用）
from localization.services import prompt_service

dflt = prompt_service.build_default_translation_template()
print("\ndefault template first user msg:")
for m in dflt:
    if m["role"] == "user":
        print(m["content"][:200])

con.close()
