"""Восстановление БД из SQL-дампа (Этап 7, бэкапы).

Запуск: python -m scripts.restore_db backups\raskidalo-local.sql
Файл БД перед восстановлением должен быть удалён или переименован.
"""

import sqlite3
import sys

from src.config.settings import DATABASE_URL

in_path = sys.argv[1] if len(sys.argv) > 1 else "backups/raskidalo-local.sql"
db_path = DATABASE_URL.replace("sqlite:///", "", 1)

with open(in_path, "r", encoding="utf-8") as f:
    script = f.read()

con = sqlite3.connect(db_path)
con.executescript(script)
con.commit()
print("restore OK <-", in_path)
