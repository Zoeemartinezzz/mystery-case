-- =====================================================================
-- MYSTERY CASE · 03_datos_ejemplo.sql
-- Datos de demostración. Ejecutar tras 01 y 02:
--   python setup_db.py
-- Los procedimientos y triggers se usan aquí también, así que el
-- historial de cada caso se rellena solo.
-- =====================================================================
USE mystery_case;
GO
DECLARE @e INT, @s INT;

INSERT INTO INVESTIGADOR (nombre, apellidos, rango, especialidad, email, rol) VALUES
(N'Marta',  N'Ortega Ruiz',   N'Comisaria',        N'Dirección',             N'marta.ortega@policia.es',  N'ADMIN'),
(N'Laura',  N'Sánchez Mora',  N'Inspectora',       N'Criminalística',        N'laura.sanchez@policia.es', N'INVESTIGADOR'),
(N'Javier', N'Molina Prieto', N'Subinspector',     N'Delitos informáticos',  N'javier.molina@policia.es', N'INVESTIGADOR'),
(N'Carmen', N'Vidal Soto',    N'Inspectora jefe',  N'Homicidios y desapariciones', N'carmen.vidal@policia.es', N'INVESTIGADOR');

INSERT INTO CASO (titulo, descripcion, lugar, fecha_apertura, prioridad, id_investigador) VALUES
(N'Robo en la joyería Aurum',        N'Robo con fuerza durante la noche; vitrina principal forzada.', N'Gran Vía, Madrid',        N'2026-02-10', N'ALTA',    2),
(N'Desaparición en el Retiro',       N'Joven desaparecido tras salir a correr.',                      N'Parque del Retiro',      N'2026-03-05', N'MEDIA',   4),
(N'Fraude bancario en línea',        N'Transferencias fraudulentas a clientes de una misma entidad.', N'Madrid (online)',         N'2026-04-01', N'CRITICA', 3),
(N'Incendio en nave industrial',     N'Incendio con indicios de haber sido provocado.',               N'Polígono Sur, nave 12',  N'2026-01-15', N'ALTA',    2),
(N'Hurto de obra en el museo',       N'Desaparece un cuadro de la sala 4 durante el horario de visitas.', N'Museo Provincial',    N'2026-05-20', N'ALTA',    4),
(N'Extorsión a comerciante',         N'Amenazas escritas exigiendo dinero a cambio de protección.',   N'Barrio de Lavapiés',     N'2026-05-28', N'CRITICA', 3),
(N'Vandalismo en estación de metro', N'Pintadas en andenes y daños en mobiliario.',                   N'Estación de Sol',        N'2026-02-25', N'BAJA',    4),
(N'Ciberataque a hospital',          N'Ransomware que cifra los sistemas de gestión de pacientes.',   N'Hospital Central',       N'2026-06-10', N'CRITICA', 3),
(N'Allanamiento de vivienda',        N'Entrada sin autorización en un domicilio particular.',         N'Chamberí',               N'2026-09-14', N'MEDIA',   4);

-- Evidencias (procedimiento almacenado: valida el caso y lo vincula)
EXEC sp_registrar_evidencia 1,N'FISICA',    N'Huellas dactilares en la vitrina de exposición', N'2026-02-10',N'Joyería Aurum',            @e OUTPUT;
EXEC sp_registrar_evidencia 1,N'DIGITAL',   N'Grabación de cámara de seguridad (23:40-00:10)', N'2026-02-10',N'Servidor de la joyería',   @e OUTPUT;
EXEC sp_registrar_evidencia 1,N'FISICA',    N'Palanca metálica abandonada',                    N'2026-02-11',N'Callejón trasero',         @e OUTPUT;
EXEC sp_registrar_evidencia 2,N'FISICA',    N'Mochila hallada junto al estanque',              N'2026-03-05',N'Parque del Retiro',        @e OUTPUT;
EXEC sp_registrar_evidencia 3,N'DIGITAL',   N'Registro de accesos desde IPs sospechosas',      N'2026-04-01',N'Servidor del banco',       @e OUTPUT;
EXEC sp_registrar_evidencia 3,N'DIGITAL',   N'Correos de phishing recibidos por las víctimas', N'2026-04-02',N'Buzones de las víctimas',  @e OUTPUT;
EXEC sp_registrar_evidencia 4,N'FISICA',    N'Restos de acelerante en el almacén',             N'2026-01-15',N'Nave 12',                  @e OUTPUT;
EXEC sp_registrar_evidencia 4,N'DOCUMENTAL',N'Informe del cuerpo de bomberos',                 N'2026-01-16',N'Parque de bomberos',       @e OUTPUT;
EXEC sp_registrar_evidencia 5,N'FISICA',    N'Marco del cuadro con restos de adhesivo',        N'2026-05-20',N'Sala 4 del museo',         @e OUTPUT;
EXEC sp_registrar_evidencia 6,N'DOCUMENTAL',N'Notas impresas de amenaza',                      N'2026-05-28',N'Comercio de la víctima',   @e OUTPUT;
EXEC sp_registrar_evidencia 7,N'DIGITAL',   N'Vídeo de las pintadas en el andén',              N'2026-02-25',N'Estación de Sol',          @e OUTPUT;
EXEC sp_registrar_evidencia 8,N'DIGITAL',   N'Volcado de memoria del servidor infectado',      N'2026-06-10',N'Sala de servidores',       @e OUTPUT;

-- La misma evidencia puede apoyar a varios casos (N:M)
INSERT INTO CASO_EVIDENCIA (id_caso, id_evidencia) VALUES (8, 6);

-- Sospechosos (procedimiento almacenado)
EXEC sp_registrar_sospechoso 1,N'Rubén', N'Castaño', N'12345678A',N'1988-04-12',N'El Gato', N'Constitución atlética, antecedentes por robo.', @s OUTPUT;
EXEC sp_registrar_sospechoso 1,N'Silvia',N'Navarro', N'23456789B',N'1991-09-30', NULL,      N'Empleada temporal de la joyería.',            @s OUTPUT;
EXEC sp_registrar_sospechoso 3,N'Óscar', N'Peña',    N'34567890C',N'1985-01-22',N'Z3r0',    N'Ingeniero informático en paro.',              @s OUTPUT;
EXEC sp_registrar_sospechoso 4,N'Tomás', N'Herrero', N'45678901D',N'1979-07-08', NULL,      N'Antiguo propietario de la nave.',             @s OUTPUT;
EXEC sp_registrar_sospechoso 6,N'Álvaro',N'Gil',     N'56789012E',N'1983-11-17',N'Gilito',  N'Conocido en el barrio por impagos.',          @s OUTPUT;
EXEC sp_registrar_sospechoso 7,N'Daniel',N'Ríos',    N'67890123F',N'2001-03-03',N'RK',      N'Miembro de un colectivo de grafiteros.',      @s OUTPUT;

-- Sospechosos vinculados a más de un caso
INSERT INTO SOSPECHOSO_CASO (id_sospechoso, id_caso, nivel_sospecha) VALUES
(1, 5, N'MEDIO'), (3, 8, N'ALTO'), (2, 5, N'BAJO');

-- Sospechosos relacionados con evidencias concretas (RF08)
INSERT INTO SOSPECHOSO_EVIDENCIA (id_sospechoso, id_evidencia, observaciones) VALUES
(1, 1,  N'Huella parcial compatible.'),
(1, 3,  N'Herramienta similar a la usada en robos anteriores.'),
(2, 2,  N'Aparece en la grabación antes del robo.'),
(3, 5,  N'IP asociada a su domicilio anterior.'),
(3, 6,  N'Dominio de envío registrado a su nombre.'),
(4, 7,  N'Tenía acceso a productos inflamables.'),
(6, 11, N'Identificado por su tatuaje en el vídeo.');

INSERT INTO TESTIGO (nombre, apellidos, telefono, direccion) VALUES
(N'Pilar',  N'Domínguez', N'600111222', N'C/ Alcalá 45, Madrid'),
(N'Andrés', N'Lozano',    N'600333444', N'C/ Mayor 12, Madrid'),
(N'Inés',   N'Cabrera',   N'600555666', N'Av. de América 8, Madrid'),
(N'Héctor', N'Ibáñez',    N'600777888', N'C/ Atocha 101, Madrid'),
(N'Rosa',   N'Marín',     N'600999000', N'Pº de la Castellana 200, Madrid');

-- Declaraciones (el trigger trg_validar_declaracion se ejecuta en cada INSERT)
INSERT INTO DECLARACION (id_caso, id_testigo, fecha_declaracion, texto) VALUES
(1, 1, N'2026-02-11 10:30:00', N'Vi a dos personas salir corriendo del callejón sobre las doce y cuarto de la noche.'),
(1, 2, N'2026-02-12 12:00:00', N'Oí un golpe seco y después la alarma de la joyería.'),
(2, 3, N'2026-03-06 09:15:00', N'Lo vi dejar la mochila junto al estanque antes de irse por el camino norte.'),
(3, 4, N'2026-04-03 17:45:00', N'Recibí una llamada del supuesto banco pidiéndome mis claves.'),
(4, 5, N'2026-01-16 11:00:00', N'Sentí olor a gasolina un rato antes de que empezara el fuego.'),
(6, 2, N'2026-05-29 16:20:00', N'El comerciante me dijo que llevaba semanas recibiendo notas anónimas.'),
(7, 1, N'2026-02-26 08:50:00', N'Vi a un chico con la cara tapada pintando junto a las escaleras.'),
(8, 4, N'2026-06-11 13:10:00', N'Los ordenadores del mostrador empezaron a pedir un rescate al mediodía.'),
(1, 1, N'2026-02-13 18:00:00', N'Recuerdo que uno de ellos llevaba una chaqueta roja.');

INSERT INTO ANALISIS_EVIDENCIA (id_evidencia, id_investigador, tipo_analisis, resultado, fecha_analisis) VALUES
(1,  2, N'Dactiloscópico',      N'Coincidencia parcial con la huella de Rubén Castaño.', N'2026-02-14'),
(3,  2, N'Dactiloscópico',      N'Sin huellas utilizables.',                              N'2026-02-15'),
(7,  2, N'Químico',             N'Presencia de gasolina en las muestras.',                N'2026-01-20'),
(5,  3, N'Forense digital',     N'Las IP pasan por un servidor proxy en el extranjero.',  N'2026-04-08'),
(12, 3, N'Análisis de malware', N'Variante de ransomware conocida; clave no recuperable.',N'2026-06-15');

-- Cierre de casos mediante el procedimiento almacenado
EXEC sp_cerrar_caso 4;
EXEC sp_cerrar_caso 7;

-- Casos pendientes (esperan resultados de laboratorio o información externa)
UPDATE CASO SET estado = N'PENDIENTE' WHERE id_caso IN (2, 6);
GO
