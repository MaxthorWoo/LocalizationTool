import sys
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect(r"e:\WebApp\LocalizationTool\localization.db")
cur = con.cursor()
# 恢复"神器传说"的原始韩语译文（测试重翻前的值）
cur.execute(
    "UPDATE entry SET translations=? WHERE id=22",
    ('{"en": "The Infinite Immortal Path", "ko": "황제의 검을 떨궈요."}',),
)
print("restored:", cur.rowcount)
con.commit()
cur.execute("SELECT translations FROM entry WHERE id=22")
print("now:", cur.fetchone()[0])
con.close()
