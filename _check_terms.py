import sys
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect(r"e:\WebApp\LocalizationTool\localization.db")
cur = con.cursor()

cur.execute("SELECT id, source_term, target_term, library_id, translations FROM termentry WHERE id=9006")
print("=== 神器传说术语完整数据 ===")
for r in cur.fetchall():
    print(r)

print("\n=== 纯文本工程相关 ===")
cur.execute("SELECT id, source_text, translations FROM entry WHERE project_id=2")
for r in cur.fetchall():
    print(r)

con.close()
