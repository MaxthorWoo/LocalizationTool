# -*- coding: utf-8 -*-
"""临时脚本：清理测试术语库。"""
import sqlite3

conn = sqlite3.connect(r"e:/WebApp/LocalizationTool/localization.db")
cur = conn.cursor()
# 删除所有非默认术语库（id > 1 的库，测试产生的）
rows = cur.execute("SELECT id, name FROM termlibrary").fetchall()
print("before:", rows)
for lid, name in rows:
    if lid != 1:
        cur.execute("DELETE FROM termentry WHERE library_id = ?", (lid,))
        cur.execute("DELETE FROM termlibrary WHERE id = ?", (lid,))
conn.commit()
print("after:", cur.execute("SELECT id, name FROM termlibrary").fetchall())
conn.close()
