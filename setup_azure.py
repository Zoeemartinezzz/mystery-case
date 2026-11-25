"""Carga las tablas, funciones, procedimientos, triggers y datos en una base de datos
YA CREADA (Azure SQL Database). No crea ni borra la base de datos, y se salta las
sentencias USE / CREATE DATABASE, que Azure SQL no admite.

Uso:   python setup_azure.py            (carga todo; aborta si ya hay tablas)
       python setup_azure.py --reset    (borra tablas y programación antes de cargar)

Lee DB_HOST, DB_PORT, DB_USER, DB_PASSWORD y DB_NAME del fichero .env
"""
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

FICHEROS = ["sql/01_schema.sql", "sql/02_programacion.sql", "sql/03_datos_ejemplo.sql"]

RESET_SQL = """
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += N'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + N'.'
             + QUOTENAME(OBJECT_NAME(parent_object_id)) + N' DROP CONSTRAINT ' + QUOTENAME(name) + N';'
  FROM sys.foreign_keys;
SELECT @sql += N'DROP TABLE ' + QUOTENAME(SCHEMA_NAME(schema_id)) + N'.' + QUOTENAME(name) + N';'
  FROM sys.tables;
SELECT @sql += N'DROP PROCEDURE ' + QUOTENAME(SCHEMA_NAME(schema_id)) + N'.' + QUOTENAME(name) + N';'
  FROM sys.procedures;
SELECT @sql += N'DROP FUNCTION ' + QUOTENAME(SCHEMA_NAME(schema_id)) + N'.' + QUOTENAME(name) + N';'
  FROM sys.objects WHERE type IN ('FN','IF','TF');
EXEC sp_executesql @sql;
"""


def bloques(texto):
    """Divide por líneas GO y adapta cada bloque a Azure SQL."""
    salida = []
    for b in re.split(r"^\s*GO\s*$", texto, flags=re.M | re.I):
        sin_comentarios = "\n".join(l for l in b.splitlines() if not l.strip().startswith("--"))
        if re.search(r"CREATE\s+DATABASE", sin_comentarios, re.I):
            continue  # la base de datos ya existe (se crea en el portal de Azure)
        sin_use = re.sub(r"^\s*USE\s+\w+\s*;?\s*$", "", b, flags=re.M | re.I).strip()
        if sin_use and any(l.strip() and not l.strip().startswith("--") for l in sin_use.splitlines()):
            salida.append(sin_use)
    return salida


def main():
    import pymssql

    try:
        conexion = pymssql.connect(
            server=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "1433"),
            user=os.getenv("DB_USER", "sa"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "mystery_case"),
            charset="UTF-8",
            tds_version="7.4",
            login_timeout=90,   # Azure serverless puede tardar ~1 min en despertar
            autocommit=True,
        )
    except pymssql.Error as e:
        sys.exit(f"No se pudo conectar: {e}\n"
                 "Revisa .env y que tu IP esté permitida en el firewall del servidor de Azure.")
    cur = conexion.cursor()

    cur.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'CASO'")
    hay_tablas = cur.fetchone()[0] > 0
    if hay_tablas and "--reset" not in sys.argv:
        sys.exit("La base de datos ya tiene tablas. Si quieres empezar de cero: python setup_azure.py --reset")
    if "--reset" in sys.argv:
        print("Borrando objetos anteriores ...")
        cur.execute(RESET_SQL)
        while cur.nextset():
            pass

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
    print("\nBase de datos cargada correctamente en Azure.")


if __name__ == "__main__":
    main()
