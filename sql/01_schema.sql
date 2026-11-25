-- =====================================================================
-- MYSTERY CASE · 01_schema.sql · DDL del modelo físico (SQL Server / T-SQL)
-- Se ejecuta con:  python setup_db.py   (entiende las líneas GO)
-- =====================================================================
USE master;
IF DB_ID('mystery_case') IS NOT NULL
BEGIN
  ALTER DATABASE mystery_case SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
  DROP DATABASE mystery_case;
END;
CREATE DATABASE mystery_case COLLATE Modern_Spanish_CI_AS;
GO
USE mystery_case;
GO

-- 1. INVESTIGADOR (también actúa como "usuario" del sistema)
CREATE TABLE INVESTIGADOR (
  id_investigador INT IDENTITY(1,1) NOT NULL,
  nombre          NVARCHAR(60)  NOT NULL,
  apellidos       NVARCHAR(100) NOT NULL,
  rango           NVARCHAR(40)  NOT NULL,
  especialidad    NVARCHAR(80)  NULL,
  email           NVARCHAR(120) NOT NULL,
  rol             VARCHAR(20)   NOT NULL CONSTRAINT df_inv_rol DEFAULT 'INVESTIGADOR',
  activo          TINYINT       NOT NULL CONSTRAINT df_inv_activo DEFAULT 1,
  fecha_alta      DATE          NOT NULL CONSTRAINT df_inv_alta DEFAULT (CAST(GETDATE() AS DATE)),
  CONSTRAINT pk_investigador PRIMARY KEY (id_investigador),
  CONSTRAINT uq_investigador_email UNIQUE (email),
  CONSTRAINT ck_inv_rol CHECK (rol IN ('ADMIN','INVESTIGADOR')),
  CONSTRAINT ck_inv_activo CHECK (activo IN (0,1))
);

-- 2. CASO (FK -> INVESTIGADOR, relación 1:N)
CREATE TABLE CASO (
  id_caso         INT IDENTITY(1,1) NOT NULL,
  titulo          NVARCHAR(150) NOT NULL,
  descripcion     NVARCHAR(MAX) NULL,
  lugar           NVARCHAR(150) NULL,
  fecha_apertura  DATE          NOT NULL CONSTRAINT df_caso_apertura DEFAULT (CAST(GETDATE() AS DATE)),
  fecha_cierre    DATE          NULL,
  estado          VARCHAR(20)   NOT NULL CONSTRAINT df_caso_estado DEFAULT 'ABIERTO',
  prioridad       VARCHAR(20)   NOT NULL CONSTRAINT df_caso_prioridad DEFAULT 'MEDIA',
  id_investigador INT           NOT NULL,
  CONSTRAINT pk_caso PRIMARY KEY (id_caso),
  CONSTRAINT fk_caso_investigador FOREIGN KEY (id_investigador)
    REFERENCES INVESTIGADOR (id_investigador),
  CONSTRAINT ck_caso_estado CHECK (estado IN ('ABIERTO','PENDIENTE','RESUELTO')),
  CONSTRAINT ck_caso_prioridad CHECK (prioridad IN ('BAJA','MEDIA','ALTA','CRITICA')),
  CONSTRAINT ck_caso_fechas CHECK (fecha_cierre IS NULL OR fecha_cierre >= fecha_apertura)
);
CREATE INDEX ix_caso_estado ON CASO (estado);

-- 3. SOSPECHOSO
CREATE TABLE SOSPECHOSO (
  id_sospechoso    INT IDENTITY(1,1) NOT NULL,
  nombre           NVARCHAR(60)  NOT NULL,
  apellidos        NVARCHAR(100) NOT NULL,
  dni              VARCHAR(15)   NULL,
  fecha_nacimiento DATE          NULL,
  alias            NVARCHAR(60)  NULL,
  descripcion      NVARCHAR(MAX) NULL,
  CONSTRAINT pk_sospechoso PRIMARY KEY (id_sospechoso)
);
-- En SQL Server un UNIQUE normal solo admite un NULL: usamos un índice filtrado.
CREATE UNIQUE INDEX uq_sospechoso_dni ON SOSPECHOSO (dni) WHERE dni IS NOT NULL;

-- 4. EVIDENCIA
CREATE TABLE EVIDENCIA (
  id_evidencia   INT IDENTITY(1,1) NOT NULL,
  tipo           VARCHAR(20)   NOT NULL,
  descripcion    NVARCHAR(255) NOT NULL,
  fecha_recogida DATE          NOT NULL,
  ubicacion      NVARCHAR(150) NULL,
  CONSTRAINT pk_evidencia PRIMARY KEY (id_evidencia),
  CONSTRAINT ck_evidencia_tipo CHECK (tipo IN ('FISICA','DIGITAL','DOCUMENTAL'))
);

-- 5. TESTIGO
CREATE TABLE TESTIGO (
  id_testigo INT IDENTITY(1,1) NOT NULL,
  nombre     NVARCHAR(60)  NOT NULL,
  apellidos  NVARCHAR(100) NOT NULL,
  telefono   VARCHAR(20)   NULL,
  direccion  NVARCHAR(150) NULL,
  CONSTRAINT pk_testigo PRIMARY KEY (id_testigo)
);

-- 6. DECLARACION (resuelve la N:M Caso–Testigo; Testigo 1:N Declaración)
CREATE TABLE DECLARACION (
  id_declaracion    INT IDENTITY(1,1) NOT NULL,
  id_caso           INT           NOT NULL,
  id_testigo        INT           NOT NULL,
  fecha_declaracion DATETIME2(0)  NOT NULL CONSTRAINT df_decl_fecha DEFAULT SYSDATETIME(),
  texto             NVARCHAR(MAX) NOT NULL,
  CONSTRAINT pk_declaracion PRIMARY KEY (id_declaracion),
  CONSTRAINT fk_decl_caso    FOREIGN KEY (id_caso)    REFERENCES CASO (id_caso),
  CONSTRAINT fk_decl_testigo FOREIGN KEY (id_testigo) REFERENCES TESTIGO (id_testigo)
);

-- 7. CASO_EVIDENCIA (N:M Caso–Evidencia)
CREATE TABLE CASO_EVIDENCIA (
  id_caso           INT          NOT NULL,
  id_evidencia      INT          NOT NULL,
  fecha_vinculacion DATETIME2(0) NOT NULL CONSTRAINT df_ce_fecha DEFAULT SYSDATETIME(),
  CONSTRAINT pk_caso_evidencia PRIMARY KEY (id_caso, id_evidencia),
  CONSTRAINT fk_ce_caso      FOREIGN KEY (id_caso)      REFERENCES CASO (id_caso) ON DELETE CASCADE,
  CONSTRAINT fk_ce_evidencia FOREIGN KEY (id_evidencia) REFERENCES EVIDENCIA (id_evidencia) ON DELETE CASCADE
);

-- 8. SOSPECHOSO_CASO (N:M Caso–Sospechoso)
CREATE TABLE SOSPECHOSO_CASO (
  id_sospechoso       INT         NOT NULL,
  id_caso             INT         NOT NULL,
  nivel_sospecha      VARCHAR(10) NOT NULL CONSTRAINT df_sc_nivel DEFAULT 'MEDIO',
  fecha_incorporacion DATE        NOT NULL CONSTRAINT df_sc_fecha DEFAULT (CAST(GETDATE() AS DATE)),
  CONSTRAINT pk_sospechoso_caso PRIMARY KEY (id_sospechoso, id_caso),
  CONSTRAINT fk_sc_sospechoso FOREIGN KEY (id_sospechoso) REFERENCES SOSPECHOSO (id_sospechoso) ON DELETE CASCADE,
  CONSTRAINT fk_sc_caso       FOREIGN KEY (id_caso)       REFERENCES CASO (id_caso) ON DELETE CASCADE,
  CONSTRAINT ck_sc_nivel CHECK (nivel_sospecha IN ('BAJO','MEDIO','ALTO'))
);

-- 9. ANALISIS_EVIDENCIA (Evidencia 1:N Análisis)
CREATE TABLE ANALISIS_EVIDENCIA (
  id_analisis     INT IDENTITY(1,1) NOT NULL,
  id_evidencia    INT           NOT NULL,
  id_investigador INT           NOT NULL,
  tipo_analisis   NVARCHAR(80)  NOT NULL,
  resultado       NVARCHAR(MAX) NOT NULL,
  fecha_analisis  DATE          NOT NULL CONSTRAINT df_an_fecha DEFAULT (CAST(GETDATE() AS DATE)),
  CONSTRAINT pk_analisis PRIMARY KEY (id_analisis),
  CONSTRAINT fk_an_evidencia    FOREIGN KEY (id_evidencia)    REFERENCES EVIDENCIA (id_evidencia),
  CONSTRAINT fk_an_investigador FOREIGN KEY (id_investigador) REFERENCES INVESTIGADOR (id_investigador)
);

-- 10. SOSPECHOSO_EVIDENCIA (RF08)
CREATE TABLE SOSPECHOSO_EVIDENCIA (
  id_sospechoso INT           NOT NULL,
  id_evidencia  INT           NOT NULL,
  observaciones NVARCHAR(255) NULL,
  CONSTRAINT pk_sospechoso_evidencia PRIMARY KEY (id_sospechoso, id_evidencia),
  CONSTRAINT fk_se_sospechoso FOREIGN KEY (id_sospechoso) REFERENCES SOSPECHOSO (id_sospechoso) ON DELETE CASCADE,
  CONSTRAINT fk_se_evidencia  FOREIGN KEY (id_evidencia)  REFERENCES EVIDENCIA (id_evidencia) ON DELETE CASCADE
);

-- 11. HISTORIAL_CASO (RF10; lo rellenan triggers)
CREATE TABLE HISTORIAL_CASO (
  id_historial INT IDENTITY(1,1) NOT NULL,
  id_caso      INT           NOT NULL,
  fecha        DATETIME2(0)  NOT NULL CONSTRAINT df_hist_fecha DEFAULT SYSDATETIME(),
  tipo_evento  VARCHAR(30)   NOT NULL,
  descripcion  NVARCHAR(255) NOT NULL,
  CONSTRAINT pk_historial PRIMARY KEY (id_historial),
  CONSTRAINT fk_hist_caso FOREIGN KEY (id_caso) REFERENCES CASO (id_caso) ON DELETE CASCADE
);
CREATE INDEX ix_historial_caso ON HISTORIAL_CASO (id_caso, fecha);
GO
