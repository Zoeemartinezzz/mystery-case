"""Crea la base de datos ejecutando los ficheros sql/01, 02 y 03 en SQL Server.

Uso:  python setup_db.py
Divide cada fichero en bloques por las líneas 'GO' (como hacen SSMS o sqlcmd)
y los ejecuta en orden. Vuelve a crear la base de datos desde cero cada vez.
"""
import os
import re
import sys

import pymssql
from dotenv import load_dotenv

load_dotenv()

FICHEROS = ["sql/01_schema.sql", "sql/02_programacion.sql", "sql/03_datos_ejemplo.sql"]


def bloques(texto):
    return [b.strip() for b in re.split(r"^\s*GO\s*$", texto, flags=re.M | re.I) if b.strip()]


def main():
    try:
        conexion = pymssql.connect(
            server=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "1433"),
            user=os.getenv("DB_USER", "sa"),
            password=os.getenv("DB_PASSWORD", ""),
            database="master",
            charset="UTF-8",
            tds_version="7.4",
            login_timeout=10,
            autocommit=True,
        )
    except pymssql.Error as e:
        sys.exit(f"No se pudo conectar con SQL Server: {e}\n"
                 "Revisa el fichero .env y que el contenedor de Docker esté en marcha (docker ps).")
    cur = conexion.cursor()
    for ruta in FICHEROS:
        print(f"Ejecutando {ruta} ...")
        with open(ruta, encoding="utf-8") as f:
            for n, bloque in enumerate(bloques(f.read()), 1):
                try:
                    cur.execute(bloque)
                    while cur.nextset():
                        pass
                except pymssql.Error as e:
                    sys.exit(f"\nError en {ruta}, bloque {n}:\n{e}\n\nBloque:\n{bloque[:400]}")
    print("\nBase de datos 'mystery_case' creada correctamente.")


if __name__ == "__main__":
    main()
