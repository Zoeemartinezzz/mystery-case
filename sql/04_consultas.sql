-- =====================================================================
-- MYSTERY CASE · 04_consultas.sql (SQL Server / T-SQL)
-- CRUD, pruebas de reglas y consultas avanzadas.
-- En TablePlus: selecciona un bloque y pulsa Cmd+Enter.
-- =====================================================================
USE mystery_case;

-- ---------------- A. OPERACIONES CRUD ----------------

-- CREATE · registrar un investigador
INSERT INTO INVESTIGADOR (nombre, apellidos, rango, especialidad, email)
VALUES (N'Lucía', N'Fernández', N'Inspectora', N'Criminalística', N'lucia.fernandez@policia.es');

-- READ · consultar los casos abiertos
SELECT * FROM CASO WHERE estado = 'ABIERTO';

-- UPDATE · cambiar la prioridad de un caso
UPDATE CASO SET prioridad = 'ALTA' WHERE id_caso = 9;

-- DELETE · eliminar una evidencia registrada por error
-- (falla si pertenece a un caso resuelto -trigger trg_proteger_evidencia- o tiene análisis)
DELETE FROM EVIDENCIA WHERE id_evidencia = 10;

-- ---------------- B. PROCEDIMIENTOS, FUNCIONES Y TRIGGERS ----------------
DECLARE @id_ev INT;
EXEC sp_registrar_evidencia 3, 'FISICA', N'Cerradura forzada', '2026-11-01', N'Puerta principal', @id_ev OUTPUT;
SELECT @id_ev AS evidencia_creada;

SELECT dbo.fn_total_evidencias_caso(1) AS evidencias_caso_1;
SELECT dbo.fn_porcentaje_casos_resueltos() AS porcentaje_resueltos;

-- Error esperado: el caso 4 está resuelto (el procedimiento lo rechaza)
-- EXEC sp_registrar_evidencia 4, 'FISICA', N'Prueba tardía', '2026-11-01', N'Nave 12', NULL;

-- Error esperado: cerrar un caso sin evidencias (trg_cerrar_caso). El caso 9 no tiene ninguna
-- UPDATE CASO SET estado = 'RESUELTO' WHERE id_caso = 9;

-- Error esperado: declaración en un caso cerrado (trg_validar_declaracion)
-- INSERT INTO DECLARACION (id_caso, id_testigo, texto) VALUES (4, 1, N'Declaración tardía');

-- Historial generado por los triggers de auditoría
SELECT * FROM HISTORIAL_CASO WHERE id_caso = 1 ORDER BY fecha DESC, id_historial DESC;

-- ---------------- C. CONSULTAS AVANZADAS (pantalla Informes) ----------------

-- 1. Casos con su investigador responsable  [JOIN]
SELECT c.id_caso, c.titulo, c.estado, c.prioridad,
       CONCAT(i.nombre, ' ', i.apellidos) AS investigador
FROM CASO c
JOIN INVESTIGADOR i ON i.id_investigador = c.id_investigador
ORDER BY c.id_caso;

-- 2. Sospechosos relacionados con cada caso  [JOIN múltiple]
SELECT c.titulo AS caso,
       CONCAT(s.nombre, ' ', s.apellidos) AS sospechoso,
       sc.nivel_sospecha
FROM SOSPECHOSO_CASO sc
JOIN CASO c        ON c.id_caso = sc.id_caso
JOIN SOSPECHOSO s  ON s.id_sospechoso = sc.id_sospechoso
ORDER BY c.id_caso, sc.nivel_sospecha DESC;

-- 3. Evidencias de cada investigación  [JOIN múltiple]
SELECT c.titulo AS caso, e.id_evidencia, e.tipo, e.descripcion, e.fecha_recogida
FROM CASO c
JOIN CASO_EVIDENCIA ce ON ce.id_caso = c.id_caso
JOIN EVIDENCIA e       ON e.id_evidencia = ce.id_evidencia
ORDER BY c.id_caso, e.fecha_recogida;

-- 4. Casos que no tienen ninguna evidencia  [LEFT JOIN + IS NULL]
SELECT c.id_caso, c.titulo, c.estado, c.fecha_apertura
FROM CASO c
LEFT JOIN CASO_EVIDENCIA ce ON ce.id_caso = c.id_caso
WHERE ce.id_evidencia IS NULL;

-- 5. Número de evidencias por investigación  [LEFT JOIN + GROUP BY + función escalar]
SELECT c.id_caso, c.titulo,
       COUNT(ce.id_evidencia)        AS evidencias,
       dbo.fn_total_evidencias_caso(c.id_caso) AS evidencias_fn
FROM CASO c
LEFT JOIN CASO_EVIDENCIA ce ON ce.id_caso = c.id_caso
GROUP BY c.id_caso, c.titulo
ORDER BY evidencias DESC, c.id_caso;

-- 6. Investigadores con más casos asignados  [GROUP BY + HAVING + subconsulta]
SELECT i.id_investigador,
       CONCAT(i.nombre, ' ', i.apellidos) AS investigador,
       COUNT(c.id_caso) AS casos
FROM INVESTIGADOR i
JOIN CASO c ON c.id_investigador = i.id_investigador
GROUP BY i.id_investigador, i.nombre, i.apellidos
HAVING COUNT(c.id_caso) = (
    SELECT MAX(t.n)
    FROM (SELECT COUNT(*) AS n FROM CASO GROUP BY id_investigador) t
);

-- 7. Testigos que han realizado más declaraciones  [GROUP BY + ORDER BY + TOP]
SELECT TOP 5 t.id_testigo,
       CONCAT(t.nombre, ' ', t.apellidos) AS testigo,
       COUNT(d.id_declaracion) AS declaraciones
FROM TESTIGO t
JOIN DECLARACION d ON d.id_testigo = t.id_testigo
GROUP BY t.id_testigo, t.nombre, t.apellidos
ORDER BY declaraciones DESC;

-- 8. Sospechosos relacionados con más de una investigación  [GROUP BY + HAVING + STRING_AGG]
SELECT s.id_sospechoso,
       CONCAT(s.nombre, ' ', s.apellidos) AS sospechoso,
       COUNT(DISTINCT sc.id_caso) AS casos,
       STRING_AGG(c.titulo, ' | ') AS investigaciones
FROM SOSPECHOSO s
JOIN SOSPECHOSO_CASO sc ON sc.id_sospechoso = s.id_sospechoso
JOIN CASO c             ON c.id_caso = sc.id_caso
GROUP BY s.id_sospechoso, s.nombre, s.apellidos
HAVING COUNT(DISTINCT sc.id_caso) > 1;

-- 9. Porcentaje de casos resueltos  [Función + agregación]
SELECT COUNT(*) AS total_casos,
       SUM(CASE WHEN estado = 'RESUELTO' THEN 1 ELSE 0 END) AS resueltos,
       dbo.fn_porcentaje_casos_resueltos() AS porcentaje_resueltos
FROM CASO;

-- 10. Investigaciones que llevan más tiempo abiertas  [Fechas + DATEDIFF + TOP]
SELECT TOP 5 id_caso, titulo, estado, fecha_apertura,
       DATEDIFF(DAY, fecha_apertura, CAST(GETDATE() AS DATE)) AS dias_abierto
FROM CASO
WHERE estado <> 'RESUELTO'
ORDER BY dias_abierto DESC;
