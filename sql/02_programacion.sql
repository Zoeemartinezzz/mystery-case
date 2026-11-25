-- =====================================================================
-- MYSTERY CASE · 02_programacion.sql (SQL Server / T-SQL)
-- Funciones, procedimientos almacenados y triggers.
-- Criterio: un caso está "cerrado" cuando su estado es RESUELTO.
-- SQL Server no tiene triggers BEFORE: se usan AFTER (con ROLLBACK + THROW)
-- e INSTEAD OF, que cumplen la misma función de validación.
-- =====================================================================
USE mystery_case;
GO

-- ===================== FUNCIONES =====================
-- Ejemplo: SELECT dbo.fn_total_evidencias_caso(1);
CREATE OR ALTER FUNCTION dbo.fn_total_evidencias_caso (@p_id_caso INT)
RETURNS INT
AS
BEGIN
  DECLARE @total INT;
  SELECT @total = COUNT(*) FROM CASO_EVIDENCIA WHERE id_caso = @p_id_caso;
  RETURN @total;
END;
GO

CREATE OR ALTER FUNCTION dbo.fn_porcentaje_casos_resueltos ()
RETURNS DECIMAL(5,2)
AS
BEGIN
  DECLARE @total INT, @resueltos INT;
  SELECT @total = COUNT(*),
         @resueltos = COALESCE(SUM(CASE WHEN estado = 'RESUELTO' THEN 1 ELSE 0 END), 0)
    FROM CASO;
  IF @total = 0 RETURN 0;
  RETURN ROUND(@resueltos * 100.0 / @total, 2);
END;
GO

-- ===================== PROCEDIMIENTOS =====================
-- sp_registrar_evidencia: 1) el caso existe 2) está abierto 3) inserta
-- 4) vincula 5) devuelve el id (parámetro OUTPUT)
-- Ejemplo:
--   DECLARE @id INT;
--   EXEC sp_registrar_evidencia 1, 'FISICA', N'Guante', '2026-03-01', N'Almacén', @id OUTPUT;
--   SELECT @id;
CREATE OR ALTER PROCEDURE sp_registrar_evidencia
  @p_id_caso      INT,
  @p_tipo         VARCHAR(20),
  @p_descripcion  NVARCHAR(255),
  @p_fecha        DATE,
  @p_ubicacion    NVARCHAR(150),
  @p_id_evidencia INT OUTPUT
AS
BEGIN
  SET NOCOUNT ON;
  SET XACT_ABORT ON;
  DECLARE @v_estado VARCHAR(20) = NULL;
  SELECT @v_estado = estado FROM CASO WHERE id_caso = @p_id_caso;

  IF @v_estado IS NULL
    THROW 50001, N'El caso indicado no existe.', 1;
  IF @v_estado = 'RESUELTO'
    THROW 50001, N'El caso está resuelto: no admite nuevas evidencias.', 1;

  BEGIN TRY
    BEGIN TRANSACTION;
      INSERT INTO EVIDENCIA (tipo, descripcion, fecha_recogida, ubicacion)
      VALUES (@p_tipo, @p_descripcion, @p_fecha, @p_ubicacion);
      SET @p_id_evidencia = SCOPE_IDENTITY();

      INSERT INTO CASO_EVIDENCIA (id_caso, id_evidencia)
      VALUES (@p_id_caso, @p_id_evidencia);
    COMMIT TRANSACTION;
  END TRY
  BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
  END CATCH
END;
GO

-- sp_cerrar_caso: 1) existe 2) no cerrado 3) tiene evidencias
-- 4) estado = RESUELTO 5) fecha de cierre.   Ejemplo: EXEC sp_cerrar_caso 1;
CREATE OR ALTER PROCEDURE sp_cerrar_caso
  @p_id_caso INT
AS
BEGIN
  SET NOCOUNT ON;
  SET XACT_ABORT ON;
  DECLARE @v_estado VARCHAR(20) = NULL;
  SELECT @v_estado = estado FROM CASO WHERE id_caso = @p_id_caso;

  IF @v_estado IS NULL
    THROW 50001, N'El caso indicado no existe.', 1;
  IF @v_estado = 'RESUELTO'
    THROW 50001, N'El caso ya está cerrado.', 1;
  IF dbo.fn_total_evidencias_caso(@p_id_caso) = 0
    THROW 50001, N'No se puede cerrar un caso sin evidencias registradas.', 1;

  BEGIN TRY
    BEGIN TRANSACTION;
      UPDATE CASO
         SET estado = 'RESUELTO',
             fecha_cierre = CAST(GETDATE() AS DATE)
       WHERE id_caso = @p_id_caso;
    COMMIT TRANSACTION;
  END TRY
  BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
  END CATCH
END;
GO

-- sp_registrar_sospechoso: 1) el caso existe 2) admite incorporaciones
-- 3) registra al sospechoso 4) lo vincula al caso
CREATE OR ALTER PROCEDURE sp_registrar_sospechoso
  @p_id_caso          INT,
  @p_nombre           NVARCHAR(60),
  @p_apellidos        NVARCHAR(100),
  @p_dni              VARCHAR(15),
  @p_fecha_nacimiento DATE,
  @p_alias            NVARCHAR(60),
  @p_descripcion      NVARCHAR(MAX),
  @p_id_sospechoso    INT OUTPUT
AS
BEGIN
  SET NOCOUNT ON;
  SET XACT_ABORT ON;
  DECLARE @v_estado VARCHAR(20) = NULL;
  SELECT @v_estado = estado FROM CASO WHERE id_caso = @p_id_caso;

  IF @v_estado IS NULL
    THROW 50001, N'El caso indicado no existe.', 1;
  IF @v_estado = 'RESUELTO'
    THROW 50001, N'El caso está resuelto: no admite nuevos sospechosos.', 1;

  BEGIN TRY
    BEGIN TRANSACTION;
      INSERT INTO SOSPECHOSO (nombre, apellidos, dni, fecha_nacimiento, alias, descripcion)
      VALUES (@p_nombre, @p_apellidos, @p_dni, @p_fecha_nacimiento, @p_alias, @p_descripcion);
      SET @p_id_sospechoso = SCOPE_IDENTITY();

      INSERT INTO SOSPECHOSO_CASO (id_sospechoso, id_caso)
      VALUES (@p_id_sospechoso, @p_id_caso);
    COMMIT TRANSACTION;
  END TRY
  BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
  END CATCH
END;
GO

-- ===================== TRIGGERS =====================
-- Impide pasar un caso a RESUELTO si no tiene evidencias.
CREATE OR ALTER TRIGGER trg_cerrar_caso
ON CASO
AFTER UPDATE
AS
BEGIN
  SET NOCOUNT ON;
  IF EXISTS (SELECT 1
               FROM inserted i
               JOIN deleted d ON d.id_caso = i.id_caso
              WHERE i.estado = 'RESUELTO' AND d.estado <> 'RESUELTO'
                AND dbo.fn_total_evidencias_caso(i.id_caso) = 0)
  BEGIN
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW 50002, N'No se puede cerrar un caso sin evidencias registradas.', 1;
  END
END;
GO

-- Fija la fecha de cierre al pasar a RESUELTO; la borra si se reabre.
CREATE OR ALTER TRIGGER trg_fecha_cierre
ON CASO
AFTER UPDATE
AS
BEGIN
  SET NOCOUNT ON;
  UPDATE c
     SET fecha_cierre = COALESCE(c.fecha_cierre, CAST(GETDATE() AS DATE))
    FROM CASO c
    JOIN inserted i ON i.id_caso = c.id_caso
    JOIN deleted d  ON d.id_caso = c.id_caso
   WHERE i.estado = 'RESUELTO' AND d.estado <> 'RESUELTO';

  UPDATE c
     SET fecha_cierre = NULL
    FROM CASO c
    JOIN inserted i ON i.id_caso = c.id_caso
   WHERE i.estado <> 'RESUELTO' AND c.fecha_cierre IS NOT NULL;
END;
GO

-- Impide registrar declaraciones en casos inexistentes o cerrados.
CREATE OR ALTER TRIGGER trg_validar_declaracion
ON DECLARACION
AFTER INSERT
AS
BEGIN
  SET NOCOUNT ON;
  IF EXISTS (SELECT 1 FROM inserted i
              WHERE NOT EXISTS (SELECT 1 FROM CASO c WHERE c.id_caso = i.id_caso))
  BEGIN
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW 50003, N'El caso indicado no existe.', 1;
  END
  IF EXISTS (SELECT 1 FROM inserted i JOIN CASO c ON c.id_caso = i.id_caso
              WHERE c.estado = 'RESUELTO')
  BEGIN
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW 50003, N'El caso está cerrado: no admite nuevas declaraciones.', 1;
  END
END;
GO

-- Protege las evidencias de casos resueltos frente a borrados.
CREATE OR ALTER TRIGGER trg_proteger_evidencia
ON EVIDENCIA
INSTEAD OF DELETE
AS
BEGIN
  SET NOCOUNT ON;
  IF EXISTS (SELECT 1
               FROM deleted d
               JOIN CASO_EVIDENCIA ce ON ce.id_evidencia = d.id_evidencia
               JOIN CASO c ON c.id_caso = ce.id_caso
              WHERE c.estado = 'RESUELTO')
  BEGIN
    THROW 50004, N'La evidencia pertenece a un caso resuelto y no puede eliminarse.', 1;
  END
  DELETE e FROM EVIDENCIA e JOIN deleted d ON d.id_evidencia = e.id_evidencia;
END;
GO

-- ---- Triggers de auditoría: alimentan HISTORIAL_CASO (RF10) ----
CREATE OR ALTER TRIGGER trg_hist_caso_alta
ON CASO
AFTER INSERT
AS
BEGIN
  SET NOCOUNT ON;
  INSERT INTO HISTORIAL_CASO (id_caso, tipo_evento, descripcion)
  SELECT id_caso, 'APERTURA', CONCAT(N'Caso abierto con prioridad ', prioridad, N'.')
    FROM inserted;
END;
GO

CREATE OR ALTER TRIGGER trg_hist_caso_cambios
ON CASO
AFTER UPDATE
AS
BEGIN
  SET NOCOUNT ON;
  INSERT INTO HISTORIAL_CASO (id_caso, tipo_evento, descripcion)
  SELECT i.id_caso, 'ESTADO', CONCAT(N'Estado: ', d.estado, N' → ', i.estado, N'.')
    FROM inserted i JOIN deleted d ON d.id_caso = i.id_caso
   WHERE i.estado <> d.estado;

  INSERT INTO HISTORIAL_CASO (id_caso, tipo_evento, descripcion)
  SELECT i.id_caso, 'PRIORIDAD', CONCAT(N'Prioridad: ', d.prioridad, N' → ', i.prioridad, N'.')
    FROM inserted i JOIN deleted d ON d.id_caso = i.id_caso
   WHERE i.prioridad <> d.prioridad;
END;
GO

CREATE OR ALTER TRIGGER trg_hist_evidencia
ON CASO_EVIDENCIA
AFTER INSERT
AS
BEGIN
  SET NOCOUNT ON;
  INSERT INTO HISTORIAL_CASO (id_caso, tipo_evento, descripcion)
  SELECT id_caso, 'EVIDENCIA', CONCAT(N'Evidencia #', id_evidencia, N' vinculada al caso.')
    FROM inserted;
END;
GO

CREATE OR ALTER TRIGGER trg_hist_sospechoso
ON SOSPECHOSO_CASO
AFTER INSERT
AS
BEGIN
  SET NOCOUNT ON;
  INSERT INTO HISTORIAL_CASO (id_caso, tipo_evento, descripcion)
  SELECT id_caso, 'SOSPECHOSO',
         CONCAT(N'Sospechoso #', id_sospechoso, N' incorporado (nivel ', nivel_sospecha, N').')
    FROM inserted;
END;
GO

CREATE OR ALTER TRIGGER trg_hist_declaracion
ON DECLARACION
AFTER INSERT
AS
BEGIN
  SET NOCOUNT ON;
  INSERT INTO HISTORIAL_CASO (id_caso, tipo_evento, descripcion)
  SELECT id_caso, 'DECLARACION', CONCAT(N'Declaración registrada del testigo #', id_testigo, N'.')
    FROM inserted;
END;
GO

-- Que las validaciones se ejecuten antes que los triggers de historial
EXEC sp_settriggerorder @triggername = 'trg_cerrar_caso',        @order = 'First', @stmttype = 'UPDATE';
EXEC sp_settriggerorder @triggername = 'trg_validar_declaracion', @order = 'First', @stmttype = 'INSERT';
GO
