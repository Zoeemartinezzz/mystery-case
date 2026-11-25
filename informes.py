"""Consultas SQL avanzadas. Las usa la página /informes y se vuelcan a sql/04_consultas.sql."""

INFORMES = [
    ("Casos con su investigador responsable",
     "JOIN",
     """SELECT c.id_caso, c.titulo, c.estado, c.prioridad,
       CONCAT(i.nombre, ' ', i.apellidos) AS investigador
FROM CASO c
JOIN INVESTIGADOR i ON i.id_investigador = c.id_investigador
ORDER BY c.id_caso"""),

    ("Sospechosos relacionados con cada caso",
     "JOIN múltiple",
     """SELECT c.titulo AS caso,
       CONCAT(s.nombre, ' ', s.apellidos) AS sospechoso,
       sc.nivel_sospecha
FROM SOSPECHOSO_CASO sc
JOIN CASO c        ON c.id_caso = sc.id_caso
JOIN SOSPECHOSO s  ON s.id_sospechoso = sc.id_sospechoso
ORDER BY c.id_caso, sc.nivel_sospecha DESC"""),

    ("Evidencias de cada investigación",
     "JOIN múltiple",
     """SELECT c.titulo AS caso, e.id_evidencia, e.tipo, e.descripcion, e.fecha_recogida
FROM CASO c
JOIN CASO_EVIDENCIA ce ON ce.id_caso = c.id_caso
JOIN EVIDENCIA e       ON e.id_evidencia = ce.id_evidencia
ORDER BY c.id_caso, e.fecha_recogida"""),

    ("Casos que no tienen ninguna evidencia",
     "LEFT JOIN + IS NULL",
     """SELECT c.id_caso, c.titulo, c.estado, c.fecha_apertura
FROM CASO c
LEFT JOIN CASO_EVIDENCIA ce ON ce.id_caso = c.id_caso
WHERE ce.id_evidencia IS NULL"""),

    ("Número de evidencias por investigación",
     "LEFT JOIN + GROUP BY + función escalar",
     """SELECT c.id_caso, c.titulo,
       COUNT(ce.id_evidencia)        AS evidencias,
       dbo.fn_total_evidencias_caso(c.id_caso) AS evidencias_fn
FROM CASO c
LEFT JOIN CASO_EVIDENCIA ce ON ce.id_caso = c.id_caso
GROUP BY c.id_caso, c.titulo
ORDER BY evidencias DESC, c.id_caso"""),

    ("Investigadores con más casos asignados",
     "GROUP BY + HAVING + subconsulta",
     """SELECT i.id_investigador,
       CONCAT(i.nombre, ' ', i.apellidos) AS investigador,
       COUNT(c.id_caso) AS casos
FROM INVESTIGADOR i
JOIN CASO c ON c.id_investigador = i.id_investigador
GROUP BY i.id_investigador, i.nombre, i.apellidos
HAVING COUNT(c.id_caso) = (
    SELECT MAX(t.n)
    FROM (SELECT COUNT(*) AS n FROM CASO GROUP BY id_investigador) t
)"""),

    ("Testigos que han realizado más declaraciones",
     "GROUP BY + ORDER BY + TOP",
     """SELECT TOP 5 t.id_testigo,
       CONCAT(t.nombre, ' ', t.apellidos) AS testigo,
       COUNT(d.id_declaracion) AS declaraciones
FROM TESTIGO t
JOIN DECLARACION d ON d.id_testigo = t.id_testigo
GROUP BY t.id_testigo, t.nombre, t.apellidos
ORDER BY declaraciones DESC"""),

    ("Sospechosos relacionados con más de una investigación",
     "GROUP BY + HAVING + STRING_AGG",
     """SELECT s.id_sospechoso,
       CONCAT(s.nombre, ' ', s.apellidos) AS sospechoso,
       COUNT(DISTINCT sc.id_caso) AS casos,
       STRING_AGG(c.titulo, ' | ') AS investigaciones
FROM SOSPECHOSO s
JOIN SOSPECHOSO_CASO sc ON sc.id_sospechoso = s.id_sospechoso
JOIN CASO c             ON c.id_caso = sc.id_caso
GROUP BY s.id_sospechoso, s.nombre, s.apellidos
HAVING COUNT(DISTINCT sc.id_caso) > 1"""),

    ("Porcentaje de casos resueltos",
     "Función + agregación",
     """SELECT COUNT(*) AS total_casos,
       SUM(CASE WHEN estado = 'RESUELTO' THEN 1 ELSE 0 END) AS resueltos,
       dbo.fn_porcentaje_casos_resueltos() AS porcentaje_resueltos
FROM CASO"""),

    ("Investigaciones que llevan más tiempo abiertas",
     "Fechas + DATEDIFF + TOP",
     """SELECT TOP 5 id_caso, titulo, estado, fecha_apertura,
       DATEDIFF(DAY, fecha_apertura, CAST(GETDATE() AS DATE)) AS dias_abierto
FROM CASO
WHERE estado <> 'RESUELTO'
ORDER BY dias_abierto DESC"""),
]
