"""Mystery Case · aplicación web de gestión de investigaciones criminales (Flask + SQL Server, pymssql)."""
import os
import re
from functools import wraps

import pymssql
from dotenv import load_dotenv
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)

from informes import INFORMES

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")

DB_CONFIG = dict(
    server=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "1433"),
    user=os.getenv("DB_USER", "sa"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "mystery_case"),
    charset="UTF-8",
    tds_version="7.4",
    login_timeout=90,
)
Error = pymssql.Error

ESTADOS = ["ABIERTO", "PENDIENTE", "RESUELTO"]
PRIORIDADES = ["BAJA", "MEDIA", "ALTA", "CRITICA"]
TIPOS_EVIDENCIA = ["FISICA", "DIGITAL", "DOCUMENTAL"]
NIVELES = ["BAJO", "MEDIO", "ALTO"]
ROLES = ["INVESTIGADOR", "ADMIN"]

NAV = [
    ("Dashboard", "/dashboard"),
    ("Investigaciones", "/casos"),
    ("Sospechosos", "/sospechosos"),
    ("Evidencias", "/evidencias"),
    ("Testigos", "/testigos"),
    ("Declaraciones", "/declaraciones"),
    ("Investigadores", "/investigadores"),
    ("Informes", "/informes"),
]


# ---------------------------------------------------------------------------
# Acceso a base de datos
# ---------------------------------------------------------------------------
def conn():
    if "db" not in g:
        g.db = pymssql.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def cerrar_conexion(_exc):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def q(sql, params=(), one=False):
    """SELECT -> lista de diccionarios (o un solo diccionario con one=True)."""
    cur = conn().cursor(as_dict=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def run(sql, params=(), devolver_id=False):
    """INSERT / UPDATE / DELETE con commit. Con devolver_id=True devuelve el id generado."""
    db = conn()
    cur = db.cursor()
    try:
        if devolver_id:
            cur.execute("SET NOCOUNT ON; " + sql + "; SELECT CAST(SCOPE_IDENTITY() AS INT);", params)
            nuevo = cur.fetchone()[0]
        else:
            cur.execute(sql, params)
            nuevo = None
        db.commit()
        return nuevo
    except Error:
        db.rollback()
        raise
    finally:
        cur.close()


def call(proc, args, con_salida=True):
    """Ejecuta un procedimiento almacenado. Si tiene parámetro OUTPUT final, devuelve su valor."""
    marcas = ", ".join("%s" for _ in args)
    if con_salida:
        sql = (f"SET NOCOUNT ON; DECLARE @salida INT; "
               f"EXEC {proc} {marcas}, @salida OUTPUT; SELECT @salida;")
    else:
        sql = f"SET NOCOUNT ON; EXEC {proc} {marcas};"
    db = conn()
    cur = db.cursor()
    try:
        cur.execute(sql, tuple(args))
        valor = cur.fetchone()[0] if con_salida else None
        db.commit()
        return valor
    except Error:
        db.rollback()
        raise
    finally:
        cur.close()


def mensaje_error(e):
    """Traduce errores de SQL Server (THROW de procedimientos/triggers, FK, UNIQUE...)."""
    numero = e.args[0] if e.args and isinstance(e.args[0], int) else 0
    texto = e.args[1] if len(e.args) > 1 else str(e)
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8", "replace")
    cuerpo = re.split(r"DB-Lib error", str(texto))[0].strip()
    if numero in (20002, 20009) or "Unable to connect" in str(texto):
        return "No se pudo conectar con SQL Server. Comprueba que Docker está encendido y el fichero .env."
    if numero == 18456 or "Login failed" in str(texto):
        return "Usuario o contraseña de SQL Server incorrectos. Revisa el fichero .env."
    if numero == 547 and "DELETE statement" in cuerpo:
        return "No se puede eliminar: el registro tiene datos relacionados."
    if numero == 547 and "CHECK" in cuerpo:
        return "Los datos no cumplen una restricción del modelo (revisa las fechas)."
    if numero in (2601, 2627):
        return "Ya existe un registro con ese valor único (email o DNI)."
    return cuerpo or str(e)  # mensajes de THROW de procedimientos y triggers


def seguro(view):
    """Captura errores de MySQL (reglas del sistema, RF12) y los muestra al usuario."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except Error as e:
            flash(mensaje_error(e), "error")
            return redirect(request.referrer or url_for("dashboard"))
    return wrapper


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("entrar"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("entrar"))
        if g.user["rol"] != "ADMIN":
            flash("Esta acción solo está disponible para administradores.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapper


@app.before_request
def cargar_usuario():
    g.user = None
    if request.endpoint in (None, "static") or "uid" not in session:
        return
    g.user = q("SELECT id_investigador, nombre, apellidos, rango, rol "
               "FROM INVESTIGADOR WHERE id_investigador = %s AND activo = 1",
               (session["uid"],), one=True)
    if g.user is None:
        session.clear()


@app.context_processor
def contexto():
    from datetime import date
    return dict(user=g.get("user"), NAV=NAV, hoy=date.today().isoformat())


@app.errorhandler(Error)
def error_bd(e):
    return render_template("error.html", msg=mensaje_error(e)), 500


# ---------------------------------------------------------------------------
# Utilidades de formularios
# ---------------------------------------------------------------------------
def nz(valor):
    valor = (valor or "").strip()
    return valor or None


def campo(name, label, tipo="text", value="", required=False, options=None):
    return dict(name=name, label=label, type=tipo,
                value="" if value is None else value,
                required=required, options=options or [])


def pantalla_form(titulo, campos, volver, boton="Guardar", aviso=None):
    return render_template("form.html", titulo=titulo, campos=campos,
                           volver=volver, boton=boton, aviso=aviso)


def opciones_investigadores():
    return [(r["id_investigador"], f"{r['nombre']} {r['apellidos']}") for r in
            q("SELECT id_investigador, nombre, apellidos FROM INVESTIGADOR "
              "WHERE activo = 1 ORDER BY apellidos")]


def opciones_casos(solo_activos=False):
    where = "WHERE estado <> 'RESUELTO'" if solo_activos else ""
    return [(r["id_caso"], f"#{r['id_caso']} · {r['titulo']}") for r in
            q(f"SELECT id_caso, titulo FROM CASO {where} ORDER BY id_caso")]


def opciones_testigos():
    return [(r["id_testigo"], f"{r['nombre']} {r['apellidos']}") for r in
            q("SELECT id_testigo, nombre, apellidos FROM TESTIGO ORDER BY apellidos")]


def lista(titulo, cols, rows, base, id_key, nuevo=None, detalle=False,
          editar=True, borrar=True, filtros=None, vacio="Todavía no hay registros."):
    return render_template("lista.html", titulo=titulo, cols=cols, rows=rows,
                           base=base, id_key=id_key, nuevo=nuevo, detalle=detalle,
                           editar=editar, borrar=borrar, filtros=filtros, vacio=vacio)


# ---------------------------------------------------------------------------
# Elegir usuario / salir
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def entrar():
    if request.method == "POST":
        u = q("SELECT id_investigador FROM INVESTIGADOR "
              "WHERE id_investigador = %s AND activo = 1",
              (request.form.get("uid"),), one=True)
        if u:
            session.clear()
            session["uid"] = u["id_investigador"]
            return redirect(url_for("dashboard"))
        flash("Elige un usuario de la lista.", "error")
    usuarios = q("SELECT id_investigador, nombre, apellidos, rango, especialidad, rol "
                 "FROM INVESTIGADOR WHERE activo = 1 ORDER BY rol, apellidos")
    return render_template("entrar.html", usuarios=usuarios)


@app.route("/salir")
def salir():
    session.clear()
    return redirect(url_for("entrar"))


# ---------------------------------------------------------------------------
# Dashboard (RF11)
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    por_estado = {e: 0 for e in ESTADOS}
    for r in q("SELECT estado, COUNT(*) AS n FROM CASO GROUP BY estado"):
        por_estado[r["estado"]] = r["n"]
    total_evidencias = q("SELECT COUNT(*) AS n FROM EVIDENCIA", one=True)["n"]
    criticas = q("SELECT COUNT(*) AS n FROM CASO "
                 "WHERE prioridad = 'CRITICA' AND estado <> 'RESUELTO'", one=True)["n"]
    porcentaje = q("SELECT dbo.fn_porcentaje_casos_resueltos() AS p", one=True)["p"]
    actividad = q("SELECT TOP 6 h.fecha, h.tipo_evento, h.descripcion, c.id_caso, c.titulo "
                  "FROM HISTORIAL_CASO h JOIN CASO c ON c.id_caso = h.id_caso "
                  "ORDER BY h.fecha DESC, h.id_historial DESC")
    recientes = q("SELECT TOP 6 c.id_caso, c.titulo, c.estado, c.prioridad, c.fecha_apertura, "
                  "CONCAT(i.nombre, ' ', i.apellidos) AS investigador, "
                  "dbo.fn_total_evidencias_caso(c.id_caso) AS evidencias "
                  "FROM CASO c JOIN INVESTIGADOR i ON i.id_investigador = c.id_investigador "
                  "ORDER BY c.fecha_apertura DESC, c.id_caso DESC")
    maximo = max(por_estado.values()) or 1
    return render_template("dashboard.html", por_estado=por_estado, maximo=maximo,
                           total_evidencias=total_evidencias, criticas=criticas,
                           porcentaje=porcentaje, actividad=actividad, recientes=recientes)


# ---------------------------------------------------------------------------
# Investigaciones / casos (RF02, RF09, RF10)
# ---------------------------------------------------------------------------
def campos_caso(v=None, con_fecha=True):
    v = v or {}
    campos = [
        campo("titulo", "Título", value=v.get("titulo"), required=True),
        campo("descripcion", "Descripción", "textarea", v.get("descripcion")),
        campo("lugar", "Lugar de los hechos", value=v.get("lugar")),
    ]
    if con_fecha:
        campos.append(campo("fecha_apertura", "Fecha de apertura", "date",
                            v.get("fecha_apertura") or "", required=True))
    campos += [
        campo("prioridad", "Prioridad", "select", v.get("prioridad", "MEDIA"),
              options=[(p, p.capitalize()) for p in PRIORIDADES]),
        campo("id_investigador", "Investigador responsable", "select",
              v.get("id_investigador") or g.user["id_investigador"],
              options=opciones_investigadores()),
    ]
    return campos


@app.route("/casos")
@login_required
def casos():
    estado = request.args.get("estado")
    sql = ("SELECT c.id_caso, c.titulo, c.estado, c.prioridad, c.fecha_apertura, "
           "CONCAT(i.nombre, ' ', i.apellidos) AS investigador, "
           "dbo.fn_total_evidencias_caso(c.id_caso) AS evidencias "
           "FROM CASO c JOIN INVESTIGADOR i ON i.id_investigador = c.id_investigador ")
    params = ()
    if estado in ESTADOS:
        sql += "WHERE c.estado = %s "
        params = (estado,)
    rows = q(sql + "ORDER BY c.id_caso DESC", params)
    cols = [("id_caso", "Nº"), ("titulo", "Investigación"), ("estado", "Estado"),
            ("prioridad", "Prioridad"), ("investigador", "Responsable"),
            ("evidencias", "Pruebas"), ("fecha_apertura", "Apertura")]
    filtros = [("Todas", "/casos"), ("Abiertas", "/casos?estado=ABIERTO"),   
            ("Pendientes", "/casos?estado=PENDIENTE"), ("Resueltas", "/casos?estado=RESUELTO")]
    return lista("Investigaciones", cols, rows, "casos", "id_caso",
                 nuevo="/casos/nuevo", detalle=True, filtros=filtros,
                 vacio="No hay investigaciones con este filtro.")


@app.route("/casos/nuevo", methods=["GET", "POST"])
@login_required
@seguro
def caso_nuevo():
    if request.method == "POST":
        f = request.form
        nuevo_id = run("INSERT INTO CASO (titulo, descripcion, lugar, fecha_apertura, "
                       "prioridad, id_investigador) VALUES (%s,%s,%s,%s,%s,%s)",
                       (f["titulo"].strip(), nz(f.get("descripcion")), nz(f.get("lugar")),
                        f["fecha_apertura"], f["prioridad"], f["id_investigador"]),
                       devolver_id=True)
        flash("Investigación creada.", "ok")
        return redirect(f"/casos/{nuevo_id}")
    from datetime import date
    return pantalla_form("Nueva investigación",
                         campos_caso({"fecha_apertura": date.today().isoformat()}),
                         "/casos", "Crear investigación")


@app.route("/casos/<int:id>")
@login_required
def caso_detalle(id):
    caso = q("SELECT c.*, CONCAT(i.nombre, ' ', i.apellidos) AS investigador, "
             "dbo.fn_total_evidencias_caso(c.id_caso) AS n_evidencias "
             "FROM CASO c JOIN INVESTIGADOR i ON i.id_investigador = c.id_investigador "
             "WHERE c.id_caso = %s", (id,), one=True)
    if not caso:
        abort(404)
    evidencias = q("SELECT e.* FROM EVIDENCIA e "
                   "JOIN CASO_EVIDENCIA ce ON ce.id_evidencia = e.id_evidencia "
                   "WHERE ce.id_caso = %s ORDER BY e.fecha_recogida", (id,))
    sospechosos = q("SELECT s.id_sospechoso, s.nombre, s.apellidos, s.alias, sc.nivel_sospecha "
                    "FROM SOSPECHOSO s JOIN SOSPECHOSO_CASO sc ON sc.id_sospechoso = s.id_sospechoso "
                    "WHERE sc.id_caso = %s ORDER BY s.apellidos", (id,))
    declaraciones = q("SELECT d.id_declaracion, d.fecha_declaracion, d.texto, "
                      "CONCAT(t.nombre, ' ', t.apellidos) AS testigo "
                      "FROM DECLARACION d JOIN TESTIGO t ON t.id_testigo = d.id_testigo "
                      "WHERE d.id_caso = %s ORDER BY d.fecha_declaracion", (id,))
    historial = q("SELECT fecha, tipo_evento, descripcion FROM HISTORIAL_CASO "
                  "WHERE id_caso = %s ORDER BY fecha DESC, id_historial DESC", (id,))
    libres_ev = [(r["id_evidencia"], f"#{r['id_evidencia']} · {r['descripcion']}") for r in
                 q("SELECT id_evidencia, descripcion FROM EVIDENCIA WHERE id_evidencia NOT IN "
                   "(SELECT id_evidencia FROM CASO_EVIDENCIA WHERE id_caso = %s)", (id,))]
    libres_sp = [(r["id_sospechoso"], f"{r['nombre']} {r['apellidos']}") for r in
                 q("SELECT id_sospechoso, nombre, apellidos FROM SOSPECHOSO WHERE id_sospechoso NOT IN "
                   "(SELECT id_sospechoso FROM SOSPECHOSO_CASO WHERE id_caso = %s)", (id,))]
    return render_template("caso_detalle.html", caso=caso, evidencias=evidencias,
                           sospechosos=sospechosos, declaraciones=declaraciones,
                           historial=historial, libres_ev=libres_ev, libres_sp=libres_sp,
                           ESTADOS=ESTADOS, NIVELES=NIVELES)


@app.route("/casos/<int:id>/editar", methods=["GET", "POST"])
@login_required
@seguro
def caso_editar(id):
    caso = q("SELECT * FROM CASO WHERE id_caso = %s", (id,), one=True)
    if not caso:
        abort(404)
    if request.method == "POST":
        f = request.form
        run("UPDATE CASO SET titulo=%s, descripcion=%s, lugar=%s, prioridad=%s, "
            "id_investigador=%s WHERE id_caso=%s",
            (f["titulo"].strip(), nz(f.get("descripcion")), nz(f.get("lugar")),
             f["prioridad"], f["id_investigador"], id))
        flash("Investigación actualizada.", "ok")
        return redirect(f"/casos/{id}")
    return pantalla_form(f"Editar investigación #{id}", campos_caso(caso, con_fecha=False),
                         f"/casos/{id}")


@app.route("/casos/<int:id>/estado", methods=["POST"])
@login_required
@seguro
def caso_estado(id):
    nuevo = request.form.get("estado")
    if nuevo not in ESTADOS:
        abort(400)
    if nuevo == "RESUELTO":
        call("sp_cerrar_caso", [id], con_salida=False)   # procedimiento almacenado
    else:
        run("UPDATE CASO SET estado = %s WHERE id_caso = %s", (nuevo, id))
    flash(f"Estado cambiado a {nuevo}.", "ok")
    return redirect(f"/casos/{id}")


@app.route("/casos/<int:id>/eliminar", methods=["POST"])
@login_required
@seguro
def caso_eliminar(id):
    run("DELETE FROM CASO WHERE id_caso = %s", (id,))
    flash("Investigación eliminada.", "ok")
    return redirect("/casos")


@app.route("/casos/<int:id>/vincular-evidencia", methods=["POST"])
@login_required
@seguro
def caso_vincular_evidencia(id):
    run("INSERT INTO CASO_EVIDENCIA (id_caso, id_evidencia) VALUES (%s, %s)",
        (id, request.form["id_evidencia"]))
    flash("Evidencia vinculada al caso.", "ok")
    return redirect(f"/casos/{id}")


@app.route("/casos/<int:id>/desvincular-evidencia/<int:eid>", methods=["POST"])
@login_required
@seguro
def caso_desvincular_evidencia(id, eid):
    run("DELETE FROM CASO_EVIDENCIA WHERE id_caso = %s AND id_evidencia = %s", (id, eid))
    flash("Evidencia desvinculada del caso.", "ok")
    return redirect(f"/casos/{id}")


@app.route("/casos/<int:id>/vincular-sospechoso", methods=["POST"])
@login_required
@seguro
def caso_vincular_sospechoso(id):
    run("INSERT INTO SOSPECHOSO_CASO (id_sospechoso, id_caso, nivel_sospecha) VALUES (%s,%s,%s)",
        (request.form["id_sospechoso"], id, request.form["nivel_sospecha"]))
    flash("Sospechoso incorporado al caso.", "ok")
    return redirect(f"/casos/{id}")


@app.route("/casos/<int:id>/desvincular-sospechoso/<int:sid>", methods=["POST"])
@login_required
@seguro
def caso_desvincular_sospechoso(id, sid):
    run("DELETE FROM SOSPECHOSO_CASO WHERE id_caso = %s AND id_sospechoso = %s", (id, sid))
    flash("Sospechoso retirado del caso.", "ok")
    return redirect(f"/casos/{id}")


# ---------------------------------------------------------------------------
# Sospechosos (RF03)
# ---------------------------------------------------------------------------
def campos_sospechoso(v=None):
    v = v or {}
    return [
        campo("nombre", "Nombre", value=v.get("nombre"), required=True),
        campo("apellidos", "Apellidos", value=v.get("apellidos"), required=True),
        campo("dni", "DNI / documento", value=v.get("dni")),
        campo("fecha_nacimiento", "Fecha de nacimiento", "date", v.get("fecha_nacimiento") or ""),
        campo("alias", "Alias", value=v.get("alias")),
        campo("descripcion", "Descripción", "textarea", v.get("descripcion")),
    ]


@app.route("/sospechosos")
@login_required
def sospechosos():
    rows = q("SELECT s.id_sospechoso, CONCAT(s.nombre, ' ', s.apellidos) AS nombre, s.dni, s.alias, "
             "COUNT(sc.id_caso) AS casos FROM SOSPECHOSO s "
             "LEFT JOIN SOSPECHOSO_CASO sc ON sc.id_sospechoso = s.id_sospechoso "
             "GROUP BY s.id_sospechoso, s.nombre, s.apellidos, s.dni, s.alias "
             "ORDER BY s.apellidos")
    cols = [("id_sospechoso", "Nº"), ("nombre", "Nombre"), ("dni", "DNI"),
            ("alias", "Alias"), ("casos", "Casos")]
    return lista("Sospechosos", cols, rows, "sospechosos", "id_sospechoso",
                 nuevo="/sospechosos/nuevo")


@app.route("/sospechosos/nuevo", methods=["GET", "POST"])
@login_required
@seguro
def sospechoso_nuevo():
    if request.method == "POST":
        f = request.form
        nuevo = call("sp_registrar_sospechoso",
                     [f["id_caso"], f["nombre"].strip(), f["apellidos"].strip(), nz(f.get("dni")),
                      nz(f.get("fecha_nacimiento")), nz(f.get("alias")), nz(f.get("descripcion"))])
        flash(f"Sospechoso #{nuevo} registrado y vinculado al caso.", "ok")
        return redirect(f"/casos/{f['id_caso']}")
    caso = request.args.get("caso", "")
    campos = [campo("id_caso", "Investigación", "select", int(caso) if caso.isdigit() else "",
                    required=True, options=opciones_casos(solo_activos=True))] + campos_sospechoso()
    return pantalla_form("Registrar sospechoso", campos, "/sospechosos", "Registrar sospechoso",
                         aviso="Se crea el sospechoso y se vincula al caso elegido (sp_registrar_sospechoso).")


@app.route("/sospechosos/<int:id>/editar", methods=["GET", "POST"])
@login_required
@seguro
def sospechoso_editar(id):
    s = q("SELECT * FROM SOSPECHOSO WHERE id_sospechoso = %s", (id,), one=True)
    if not s:
        abort(404)
    if request.method == "POST":
        f = request.form
        run("UPDATE SOSPECHOSO SET nombre=%s, apellidos=%s, dni=%s, fecha_nacimiento=%s, "
            "alias=%s, descripcion=%s WHERE id_sospechoso=%s",
            (f["nombre"].strip(), f["apellidos"].strip(), nz(f.get("dni")),
             nz(f.get("fecha_nacimiento")), nz(f.get("alias")), nz(f.get("descripcion")), id))
        flash("Sospechoso actualizado.", "ok")
        return redirect("/sospechosos")
    return pantalla_form(f"Editar sospechoso #{id}", campos_sospechoso(s), "/sospechosos")


@app.route("/sospechosos/<int:id>/eliminar", methods=["POST"])
@login_required
@seguro
def sospechoso_eliminar(id):
    run("DELETE FROM SOSPECHOSO WHERE id_sospechoso = %s", (id,))
    flash("Sospechoso eliminado.", "ok")
    return redirect("/sospechosos")


# ---------------------------------------------------------------------------
# Evidencias y análisis (RF04, RF05, RF08)
# ---------------------------------------------------------------------------
def campos_evidencia(v=None):
    v = v or {}
    return [
        campo("tipo", "Tipo", "select", v.get("tipo", "FISICA"),
              options=[(t, t.capitalize()) for t in TIPOS_EVIDENCIA]),
        campo("descripcion", "Descripción", value=v.get("descripcion"), required=True),
        campo("fecha_recogida", "Fecha de recogida", "date", v.get("fecha_recogida") or "", required=True),
        campo("ubicacion", "Ubicación", value=v.get("ubicacion")),
    ]


@app.route("/evidencias")
@login_required
def evidencias():
    rows = q("SELECT e.id_evidencia, e.tipo, e.descripcion, e.fecha_recogida, e.ubicacion, "
             "STRING_AGG(CONCAT('#', ce.id_caso), ' ') WITHIN GROUP (ORDER BY ce.id_caso) AS casos, "
             "(SELECT COUNT(*) FROM ANALISIS_EVIDENCIA a WHERE a.id_evidencia = e.id_evidencia) AS analisis "
             "FROM EVIDENCIA e LEFT JOIN CASO_EVIDENCIA ce ON ce.id_evidencia = e.id_evidencia "
             "GROUP BY e.id_evidencia, e.tipo, e.descripcion, e.fecha_recogida, e.ubicacion "
             "ORDER BY e.id_evidencia DESC")
    cols = [("id_evidencia", "Nº"), ("tipo", "Tipo"), ("descripcion", "Descripción"),
            ("fecha_recogida", "Recogida"), ("casos", "Casos"), ("analisis", "Análisis")]
    return lista("Evidencias", cols, rows, "evidencias", "id_evidencia",
                 nuevo="/evidencias/nueva", detalle=True)


@app.route("/evidencias/nueva", methods=["GET", "POST"])
@login_required
@seguro
def evidencia_nueva():
    if request.method == "POST":
        f = request.form
        nueva = call("sp_registrar_evidencia",
                    [f["id_caso"], f["tipo"], f["descripcion"].strip(),
                     f["fecha_recogida"], nz(f.get("ubicacion"))])
        flash(f"Evidencia #{nueva} registrada y vinculada al caso.", "ok")
        return redirect(f"/evidencias/{nueva}")
    from datetime import date
    caso = request.args.get("caso", "")
    campos = [campo("id_caso", "Investigación", "select", int(caso) if caso.isdigit() else "",
                    required=True, options=opciones_casos(solo_activos=True))]
    campos += campos_evidencia({"fecha_recogida": date.today().isoformat()})
    return pantalla_form("Registrar evidencia", campos, "/evidencias", "Registrar evidencia",
                         aviso="Se crea la evidencia y se vincula al caso (sp_registrar_evidencia).")


@app.route("/evidencias/<int:id>")
@login_required
def evidencia_detalle(id):
    ev = q("SELECT * FROM EVIDENCIA WHERE id_evidencia = %s", (id,), one=True)
    if not ev:
        abort(404)
    casos_ev = q("SELECT c.id_caso, c.titulo, c.estado FROM CASO c "
                 "JOIN CASO_EVIDENCIA ce ON ce.id_caso = c.id_caso WHERE ce.id_evidencia = %s", (id,))
    analisis = q("SELECT a.id_analisis, a.tipo_analisis, a.resultado, a.fecha_analisis, "
                 "CONCAT(i.nombre, ' ', i.apellidos) AS analista "
                 "FROM ANALISIS_EVIDENCIA a JOIN INVESTIGADOR i ON i.id_investigador = a.id_investigador "
                 "WHERE a.id_evidencia = %s ORDER BY a.fecha_analisis", (id,))
    sospechosos_ev = q("SELECT s.id_sospechoso, CONCAT(s.nombre, ' ', s.apellidos) AS nombre, se.observaciones "
                       "FROM SOSPECHOSO s JOIN SOSPECHOSO_EVIDENCIA se ON se.id_sospechoso = s.id_sospechoso "
                       "WHERE se.id_evidencia = %s", (id,))
    libres = [(r["id_sospechoso"], f"{r['nombre']} {r['apellidos']}") for r in
              q("SELECT id_sospechoso, nombre, apellidos FROM SOSPECHOSO WHERE id_sospechoso NOT IN "
                "(SELECT id_sospechoso FROM SOSPECHOSO_EVIDENCIA WHERE id_evidencia = %s)", (id,))]
    return render_template("evidencia_detalle.html", ev=ev, casos_ev=casos_ev, analisis=analisis,
                           sospechosos_ev=sospechosos_ev, libres=libres)


@app.route("/evidencias/<int:id>/editar", methods=["GET", "POST"])
@login_required
@seguro
def evidencia_editar(id):
    ev = q("SELECT * FROM EVIDENCIA WHERE id_evidencia = %s", (id,), one=True)
    if not ev:
        abort(404)
    if request.method == "POST":
        f = request.form
        run("UPDATE EVIDENCIA SET tipo=%s, descripcion=%s, fecha_recogida=%s, ubicacion=%s "
            "WHERE id_evidencia=%s",
            (f["tipo"], f["descripcion"].strip(), f["fecha_recogida"], nz(f.get("ubicacion")), id))
        flash("Evidencia actualizada.", "ok")
        return redirect(f"/evidencias/{id}")
    return pantalla_form(f"Editar evidencia #{id}", campos_evidencia(ev), f"/evidencias/{id}")


@app.route("/evidencias/<int:id>/eliminar", methods=["POST"])
@login_required
@seguro
def evidencia_eliminar(id):
    run("DELETE FROM EVIDENCIA WHERE id_evidencia = %s", (id,))
    flash("Evidencia eliminada.", "ok")
    return redirect("/evidencias")


@app.route("/evidencias/<int:id>/analisis", methods=["POST"])
@login_required
@seguro
def analisis_nuevo(id):
    f = request.form
    run("INSERT INTO ANALISIS_EVIDENCIA (id_evidencia, id_investigador, tipo_analisis, resultado, fecha_analisis) "
        "VALUES (%s,%s,%s,%s,%s)",
        (id, g.user["id_investigador"], f["tipo_analisis"].strip(), f["resultado"].strip(), f["fecha_analisis"]))
    flash("Análisis registrado.", "ok")
    return redirect(f"/evidencias/{id}")


@app.route("/evidencias/<int:id>/analisis/<int:aid>/eliminar", methods=["POST"])
@login_required
@seguro
def analisis_eliminar(id, aid):
    run("DELETE FROM ANALISIS_EVIDENCIA WHERE id_analisis = %s", (aid,))
    flash("Análisis eliminado.", "ok")
    return redirect(f"/evidencias/{id}")


@app.route("/evidencias/<int:id>/sospechoso", methods=["POST"])
@login_required
@seguro
def evidencia_vincular_sospechoso(id):
    run("INSERT INTO SOSPECHOSO_EVIDENCIA (id_sospechoso, id_evidencia, observaciones) VALUES (%s,%s,%s)",
        (request.form["id_sospechoso"], id, nz(request.form.get("observaciones"))))
    flash("Sospechoso relacionado con la evidencia.", "ok")
    return redirect(f"/evidencias/{id}")


@app.route("/evidencias/<int:id>/sospechoso/<int:sid>/eliminar", methods=["POST"])
@login_required
@seguro
def evidencia_desvincular_sospechoso(id, sid):
    run("DELETE FROM SOSPECHOSO_EVIDENCIA WHERE id_sospechoso = %s AND id_evidencia = %s", (sid, id))
    flash("Relación eliminada.", "ok")
    return redirect(f"/evidencias/{id}")


# ---------------------------------------------------------------------------
# Testigos (RF06)
# ---------------------------------------------------------------------------
def campos_testigo(v=None):
    v = v or {}
    return [
        campo("nombre", "Nombre", value=v.get("nombre"), required=True),
        campo("apellidos", "Apellidos", value=v.get("apellidos"), required=True),
        campo("telefono", "Teléfono", value=v.get("telefono")),
        campo("direccion", "Dirección", value=v.get("direccion")),
    ]


@app.route("/testigos")
@login_required
def testigos():
    rows = q("SELECT t.id_testigo, CONCAT(t.nombre, ' ', t.apellidos) AS nombre, t.telefono, t.direccion, "
             "COUNT(d.id_declaracion) AS declaraciones FROM TESTIGO t "
             "LEFT JOIN DECLARACION d ON d.id_testigo = t.id_testigo "
             "GROUP BY t.id_testigo, t.nombre, t.apellidos, t.telefono, t.direccion ORDER BY t.apellidos")
    cols = [("id_testigo", "Nº"), ("nombre", "Nombre"), ("telefono", "Teléfono"),
            ("direccion", "Dirección"), ("declaraciones", "Declaraciones")]
    return lista("Testigos", cols, rows, "testigos", "id_testigo", nuevo="/testigos/nuevo")


@app.route("/testigos/nuevo", methods=["GET", "POST"])
@login_required
@seguro
def testigo_nuevo():
    if request.method == "POST":
        f = request.form
        run("INSERT INTO TESTIGO (nombre, apellidos, telefono, direccion) VALUES (%s,%s,%s,%s)",
            (f["nombre"].strip(), f["apellidos"].strip(), nz(f.get("telefono")), nz(f.get("direccion"))))
        flash("Testigo registrado.", "ok")
        return redirect("/testigos")
    return pantalla_form("Registrar testigo", campos_testigo(), "/testigos", "Registrar testigo")


@app.route("/testigos/<int:id>/editar", methods=["GET", "POST"])
@login_required
@seguro
def testigo_editar(id):
    t = q("SELECT * FROM TESTIGO WHERE id_testigo = %s", (id,), one=True)
    if not t:
        abort(404)
    if request.method == "POST":
        f = request.form
        run("UPDATE TESTIGO SET nombre=%s, apellidos=%s, telefono=%s, direccion=%s WHERE id_testigo=%s",
            (f["nombre"].strip(), f["apellidos"].strip(), nz(f.get("telefono")), nz(f.get("direccion")), id))
        flash("Testigo actualizado.", "ok")
        return redirect("/testigos")
    return pantalla_form(f"Editar testigo #{id}", campos_testigo(t), "/testigos")


@app.route("/testigos/<int:id>/eliminar", methods=["POST"])
@login_required
@seguro
def testigo_eliminar(id):
    run("DELETE FROM TESTIGO WHERE id_testigo = %s", (id,))
    flash("Testigo eliminado.", "ok")
    return redirect("/testigos")


# ---------------------------------------------------------------------------
# Declaraciones (RF07)
# ---------------------------------------------------------------------------
@app.route("/declaraciones")
@login_required
def declaraciones():
    rows = q("SELECT d.id_declaracion, d.fecha_declaracion, "
             "CONCAT('#', c.id_caso, ' · ', c.titulo) AS caso, "
             "CONCAT(t.nombre, ' ', t.apellidos) AS testigo, "
             "CASE WHEN LEN(d.texto) > 90 THEN CONCAT(LEFT(d.texto, 90), '…') ELSE d.texto END AS texto "
             "FROM DECLARACION d JOIN CASO c ON c.id_caso = d.id_caso "
             "JOIN TESTIGO t ON t.id_testigo = d.id_testigo ORDER BY d.fecha_declaracion DESC")
    cols = [("id_declaracion", "Nº"), ("fecha_declaracion", "Fecha"), ("caso", "Investigación"),
            ("testigo", "Testigo"), ("texto", "Declaración")]
    return lista("Declaraciones", cols, rows, "declaraciones", "id_declaracion",
                 nuevo="/declaraciones/nueva")


@app.route("/declaraciones/nueva", methods=["GET", "POST"])
@login_required
@seguro
def declaracion_nueva():
    if request.method == "POST":
        f = request.form
        run("INSERT INTO DECLARACION (id_caso, id_testigo, texto) VALUES (%s,%s,%s)",
            (f["id_caso"], f["id_testigo"], f["texto"].strip()))
        flash("Declaración registrada.", "ok")
        return redirect(f"/casos/{f['id_caso']}")
    caso = request.args.get("caso", "")
    campos = [
        campo("id_caso", "Investigación", "select", int(caso) if caso.isdigit() else "",
              required=True, options=opciones_casos(solo_activos=True)),
        campo("id_testigo", "Testigo", "select", "", required=True, options=opciones_testigos()),
        campo("texto", "Declaración", "textarea", "", required=True),
    ]
    return pantalla_form("Registrar declaración", campos, "/declaraciones", "Registrar declaración",
                         aviso="El trigger trg_validar_declaracion rechaza casos inexistentes o cerrados.")


@app.route("/declaraciones/<int:id>/editar", methods=["GET", "POST"])
@login_required
@seguro
def declaracion_editar(id):
    d = q("SELECT * FROM DECLARACION WHERE id_declaracion = %s", (id,), one=True)
    if not d:
        abort(404)
    if request.method == "POST":
        run("UPDATE DECLARACION SET texto=%s WHERE id_declaracion=%s", (request.form["texto"].strip(), id))
        flash("Declaración actualizada.", "ok")
        return redirect("/declaraciones")
    return pantalla_form(f"Editar declaración #{id}",
                         [campo("texto", "Declaración", "textarea", d["texto"], required=True)],
                         "/declaraciones")


@app.route("/declaraciones/<int:id>/eliminar", methods=["POST"])
@login_required
@seguro
def declaracion_eliminar(id):
    run("DELETE FROM DECLARACION WHERE id_declaracion = %s", (id,))
    flash("Declaración eliminada.", "ok")
    return redirect("/declaraciones")


# ---------------------------------------------------------------------------
# Investigadores (RF01) · solo el administrador modifica
# ---------------------------------------------------------------------------
def campos_investigador(v=None):
    v = v or {}
    return [
        campo("nombre", "Nombre", value=v.get("nombre"), required=True),
        campo("apellidos", "Apellidos", value=v.get("apellidos"), required=True),
        campo("rango", "Rango", value=v.get("rango"), required=True),
        campo("especialidad", "Especialidad", value=v.get("especialidad")),
        campo("email", "Correo electrónico", "email", v.get("email"), required=True),
        campo("rol", "Rol", "select", v.get("rol", "INVESTIGADOR"),
              options=[(r, r.capitalize()) for r in ROLES]),
        campo("activo", "Estado de la cuenta", "select", v.get("activo", 1),
              options=[(1, "Activa"), (0, "Desactivada")]),
    ]


@app.route("/investigadores")
@login_required
def investigadores():
    rows = q("SELECT i.id_investigador, CONCAT(i.nombre, ' ', i.apellidos) AS nombre, i.rango, "
             "i.especialidad, i.email, i.rol, COUNT(c.id_caso) AS casos "
             "FROM INVESTIGADOR i LEFT JOIN CASO c ON c.id_investigador = i.id_investigador "
             "GROUP BY i.id_investigador, i.nombre, i.apellidos, i.rango, i.especialidad, i.email, i.rol "
             "ORDER BY i.apellidos")
    cols = [("id_investigador", "Nº"), ("nombre", "Nombre"), ("rango", "Rango"),
            ("especialidad", "Especialidad"), ("email", "Correo"), ("rol", "Rol"), ("casos", "Casos")]
    es_admin = g.user["rol"] == "ADMIN"
    return lista("Investigadores", cols, rows, "investigadores", "id_investigador",
                 nuevo="/investigadores/nuevo" if es_admin else None,
                 editar=es_admin, borrar=es_admin)


@app.route("/investigadores/nuevo", methods=["GET", "POST"])
@admin_required
@seguro
def investigador_nuevo():
    if request.method == "POST":
        f = request.form
        run("INSERT INTO INVESTIGADOR (nombre, apellidos, rango, especialidad, email, rol, activo) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (f["nombre"].strip(), f["apellidos"].strip(), f["rango"].strip(), nz(f.get("especialidad")),
             f["email"].strip(), f["rol"], f["activo"]))
        flash("Investigador registrado.", "ok")
        return redirect("/investigadores")
    return pantalla_form("Registrar investigador", campos_investigador(), "/investigadores",
                         "Registrar investigador")


@app.route("/investigadores/<int:id>/editar", methods=["GET", "POST"])
@admin_required
@seguro
def investigador_editar(id):
    i = q("SELECT * FROM INVESTIGADOR WHERE id_investigador = %s", (id,), one=True)
    if not i:
        abort(404)
    if request.method == "POST":
        f = request.form
        run("UPDATE INVESTIGADOR SET nombre=%s, apellidos=%s, rango=%s, especialidad=%s, email=%s, "
            "rol=%s, activo=%s WHERE id_investigador=%s",
            (f["nombre"].strip(), f["apellidos"].strip(), f["rango"].strip(), nz(f.get("especialidad")),
             f["email"].strip(), f["rol"], f["activo"], id))
        flash("Investigador actualizado.", "ok")
        return redirect("/investigadores")
    return pantalla_form(f"Editar investigador #{id}", campos_investigador(i), "/investigadores")


@app.route("/investigadores/<int:id>/eliminar", methods=["POST"])
@admin_required
@seguro
def investigador_eliminar(id):
    if id == g.user["id_investigador"]:
        flash("No puedes eliminar tu propio usuario.", "error")
        return redirect("/investigadores")
    run("DELETE FROM INVESTIGADOR WHERE id_investigador = %s", (id,))
    flash("Investigador eliminado.", "ok")
    return redirect("/investigadores")


# ---------------------------------------------------------------------------
# Informes: consultas SQL avanzadas
# ---------------------------------------------------------------------------
@app.route("/informes")
@login_required
def informes():
    resultados = []
    for titulo, tecnica, sql in INFORMES:
        filas = q(sql)
        resultados.append(dict(titulo=titulo, tecnica=tecnica, sql=sql, filas=filas,
                               columnas=list(filas[0].keys()) if filas else []))
    return render_template("informes.html", resultados=resultados)


if __name__ == "__main__":
    app.run(debug=True)
