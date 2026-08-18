# -*- coding: utf-8 -*-
"""临时排查：当前术语库与工程状态。"""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

conn = sqlite3.connect(r"e:/WebApp/LocalizationTool/localization.db")
cur = conn.cursor()

print("=== 工程（source_lang）===")
for r in cur.execute("SELECT id, name, source_lang FROM project").fetchall():
    print(" ", r)

print("\n=== 术语库（id, name, source_lang, 术语数）===")
for r in cur.execute(
    """
    SELECT l.id, l.name, l.source_lang, COUNT(e.id)
    FROM termlibrary l LEFT JOIN termentry e ON e.library_id = l.id
    GROUP BY l.id
    """
).fetchall():
    print(" ", r)

print("\n=== 语言方案行（term_library_id）===")
for r in cur.execute(
    "SELECT id, project_id, lang_code, term_library_id, enabled FROM projectlangconfig"
).fetchall():
    print(" ", r)

print("\n=== 默认术语库中含'神'的术语 ===")
for r in cur.execute(
    "SELECT id, library_id, source_term, target_term FROM termentry WHERE library_id=1 AND source_term LIKE '%神%'"
).fetchall():
    print(" ", r)

conn.close()
