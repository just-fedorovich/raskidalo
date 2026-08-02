"""SQL-дамп БД в файл (Этап 7, бэкапы).

Запуск: python -m scripts.dump_db backups\raskidalo-local.sql
Аргумент "-" — печатать в консоль (для облачного дампа через railway ssh).

Файл пишется самим скриптом в UTF-8: конвейер PowerShell в системной
кодировке Windows превращал кириллицу в "?" (блок 7.C.5).
"""

import sqlite3
import sys

from src.config.settings import DATABASE_URL

out_path = sys.argv[1] if len(sys.argv) > 1 else "backups/raskidalo-local.sql"
db_path = DATABASE_URL.replace("sqlite:///", "", 1)
con = sqlite3.connect(db_path)

if out_path == "-":
    sys.stdout.reconfigure(encoding="utf-8")
    for line in con.iterdump():
        print(line)
else:
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for line in con.iterdump():
            f.write(line + "\n")
    print("dump OK ->", out_path)
