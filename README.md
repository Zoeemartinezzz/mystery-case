# Mystery Case · Sistema inteligente de investigación criminal

Aplicación web (Flask + **SQL Server**) para gestionar casos criminales, investigadores,
sospechosos, evidencias, testigos y declaraciones. Proyecto de Bases de Datos.

## Estructura

```
app.py                   Aplicación Flask (rutas y acceso a SQL Server con pymssql)
setup_db.py              Crea la base de datos ejecutando los ficheros de sql/
informes.py              Consultas SQL avanzadas (pantalla "Informes")
templates/  static/      Interfaz HTML/CSS
sql/01_schema.sql        DDL del modelo físico (11 tablas)
sql/02_programacion.sql  Funciones, procedimientos almacenados y triggers (T-SQL)
sql/03_datos_ejemplo.sql Datos de demostración
sql/04_consultas.sql     CRUD, pruebas de reglas y consultas avanzadas
docs/diccionario_datos.xlsx Diccionario de datos
```

## Puesta en marcha

Requisitos: **Git**, **Python 3.10 o superior** y **Docker Desktop** (abierto y en marcha).
No hace falta instalar ningún driver ODBC.

1. **Descargar el proyecto**
   ```bash
   git clone https://github.com/Zoeemartinezzz/mystery-case.git
   cd mystery-case
   ```

2. **Arrancar SQL Server con Docker** (una sola línea; la contraseña es de ejemplo, puedes cambiarla):
   ```bash
   docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=Mystery2026x" -p 1433:1433 --name sqlserver -d mcr.microsoft.com/mssql/server:2022-latest
   ```
   Espera 30-60 segundos a que arranque. En Mac con chip M (Apple Silicon) Docker avisará de que la imagen es `amd64`; es normal.

3. **Crear el entorno de Python e instalar dependencias**

   macOS / Linux:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   Windows (PowerShell):
   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. **Configurar la conexión**: copia `.env.example` a `.env` y rellénalo.
   ```bash
   cp .env.example .env        # en Windows: copy .env.example .env
   ```
   Contenido del `.env` (la contraseña debe ser la misma que pusiste en `docker run`):
   ```
   DB_HOST=localhost
   DB_PORT=1433
   DB_USER=sa
   DB_PASSWORD=Mystery2026x
   DB_NAME=mystery_case
   SECRET_KEY=cualquier_texto_largo
   ```

5. **Crear la base de datos y cargar los datos de ejemplo**
   ```bash
   python setup_db.py
   ```
   Debe terminar con "Base de datos 'mystery_case' creada correctamente."

6. **Lanzar la web**
   ```bash
   flask --app app run
   ```
   y abrir http://127.0.0.1:5000 en el navegador. Para detenerla, `Ctrl + C`.

### Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `failed to connect to the docker API` | Abre Docker Desktop y espera a que diga "Engine running". |
| `The container name "/sqlserver" is already in use` | `docker start sqlserver` (si ya existe) o `docker rm -f sqlserver` y repite el paso 2. |
| `Login failed for user 'sa'` | La contraseña del `.env` no coincide con la del contenedor, o SQL Server aún está arrancando (espera un minuto). |
| `Address already in use` | Otro programa usa el puerto 5000: `flask --app app run --port 5001`. |

Para ver los datos con un cliente (TablePlus, Azure Data Studio, DBeaver): servidor `localhost`, puerto `1433`, usuario `sa`, base de datos `mystery_case`.

## Qué cubre el enunciado

| Requisito | Dónde |
|---|---|
| ≥ 5 tablas, ≥ 2 con FK | 11 tablas, 9 con FK (`01_schema.sql`) |
| Inserciones, consultas, actualizaciones y borrados | Todas las pantallas; ejemplos en `04_consultas.sql` |
| Procedimientos almacenados | `sp_registrar_evidencia`, `sp_cerrar_caso`, `sp_registrar_sospechoso` |
| Triggers | `trg_cerrar_caso`, `trg_fecha_cierre`, `trg_validar_declaracion`, `trg_proteger_evidencia` y 5 de historial |
| Funciones | `dbo.fn_total_evidencias_caso`, `dbo.fn_porcentaje_casos_resueltos` |
| Diccionario de datos | `docs/diccionario_datos.xlsx` |

SQL Server no tiene triggers `BEFORE`: las validaciones usan triggers `AFTER` con `ROLLBACK` + `THROW`
(y `INSTEAD OF` para proteger el borrado de evidencias).

## Perfiles y reglas

- **Administrador**: además de lo del investigador, gestiona investigadores. **Investigador**: casos, sospechosos, evidencias, testigos y declaraciones.
- La elección de usuario no usa contraseña, como pide el enunciado.
- No se registran evidencias, sospechosos ni declaraciones en casos resueltos; no se cierra un caso sin evidencias; no se borran evidencias de casos resueltos o con análisis.

## Subir a GitHub

```bash
git init && git add . && git commit -m "Mystery Case: proyecto inicial"
git branch -M main
git remote add origin https://github.com/Zoeemartinezzz/mystery-case.git
git push -u origin main
```
El fichero `.env` está en `.gitignore`: no subas tu contraseña.
