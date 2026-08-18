# -*- coding: utf-8 -*-
"""临时排查：语言方案行结构。"""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

conn = sqlite3.connect(r"e:/WebApp/LocalizationTool/localization.db")
cur = conn.cursor()

print("=== projectlangconfig 列 ===")
for r in cur.execute("PRAGMA table_info(projectlangconfig)").fetchall():
    print(" ", r)

print("\n=== 工程 1 方案行 ===")
rows = cur.execute("SELECT * FROM projectlangconfig WHERE project_id=1").fetchall()
for r in rows:
    print(" ", r)

conn.close()
