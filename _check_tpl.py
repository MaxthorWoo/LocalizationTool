import sys
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect(r"e:\WebApp\LocalizationTool\localization.db")
cur = con.cursor()
cur.execute("SELECT id, name, messages FROM prompttemplate")
for rid, name, messages in cur.fetchall():
    print("=" * 70)
    print(f"template id={rid} name={name}")
    print(messages)
    print()
con.close()
