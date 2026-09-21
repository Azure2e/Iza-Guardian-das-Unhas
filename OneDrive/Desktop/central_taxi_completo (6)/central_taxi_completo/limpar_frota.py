"""Esvazia taxistas de demonstração. Mantém admin, rotas e passageiros."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "taxi.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
drivers = list(cur.execute("SELECT id, user_id FROM drivers"))
for d in drivers:
    cur.execute("UPDATE rides SET driver_id=NULL WHERE driver_id=?", (d["id"],))
    cur.execute("DELETE FROM payments WHERE driver_id=?", (d["id"],))
    cur.execute("DELETE FROM drivers WHERE id=?", (d["id"],))
    cur.execute("DELETE FROM users WHERE id=? AND role='motorista'", (d["user_id"],))
con.commit()
left = cur.execute("SELECT COUNT(*) AS c FROM drivers").fetchone()["c"]
con.close()
print(f"Removidos {len(drivers)} taxista(s). Frota agora: {left}.")
print("Cadastre os motoristas reais em Admin > Motoristas.")
