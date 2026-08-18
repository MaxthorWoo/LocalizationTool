import sys
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect(r"e:\WebApp\LocalizationTool\localization.db")
cur = con.cursor()
cur.execute("SELECT id, source_text, status, translations FROM entry WHERE project_id=2")
for r in cur.fetchall():
    print(r[0], r[1], r[2], str(r[3])[:120])
con.close()
