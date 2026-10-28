-- Bases PostgreSQL creadas antes del estado "obstruido" y de la duración en el estado.
-- Las bases nuevas ya nacen con este esquema (db/schema.sql); las SQLite se migran solas al iniciar la API.
-- Sin probar contra un servidor PostgreSQL real: revísalo en una copia antes de aplicarlo.

ALTER TABLE espacios ADD COLUMN IF NOT EXISTS estado_desde TIMESTAMP WITH TIME ZONE;
ALTER TABLE espacios ADD COLUMN IF NOT EXISTS inicio_observado BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE espacios ADD COLUMN IF NOT EXISTS objeto VARCHAR(40);

ALTER TABLE espacios DROP CONSTRAINT IF EXISTS estadoespacio;
ALTER TABLE espacios ADD CONSTRAINT estadoespacio
    CHECK (estado IN ('libre', 'ocupado', 'reservado', 'fuera_de_servicio', 'obstruido'));

ALTER TABLE eventos DROP CONSTRAINT IF EXISTS tipoevento;
ALTER TABLE eventos ADD CONSTRAINT tipoevento
    CHECK (tipo IN ('entrada', 'salida', 'cambio_ocupacion', 'error_deteccion', 'camara_desconectada',
                    'camara_restablecida', 'obstruccion', 'obstruccion_retirada'));
