-- Generado por scripts/export_schema.py. No editar a mano: cambia api/app/models.py.

CREATE TABLE usuarios (
	id SERIAL NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	correo VARCHAR(160) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	rol VARCHAR(30) NOT NULL, 
	activo BOOLEAN NOT NULL, 
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT rol CHECK (rol IN ('estudiante', 'docente', 'directivo', 'administrativo', 'externo', 'admin'))
);

CREATE UNIQUE INDEX ix_usuarios_correo ON usuarios (correo);

CREATE TABLE zonas (
	id SERIAL NOT NULL, 
	nombre VARCHAR(40) NOT NULL, 
	descripcion VARCHAR(200), 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
);

CREATE TABLE camaras (
	id SERIAL NOT NULL, 
	codigo VARCHAR(40) NOT NULL, 
	zona_id INTEGER NOT NULL, 
	estado VARCHAR(30) NOT NULL, 
	ultima_senal TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	FOREIGN KEY(zona_id) REFERENCES zonas (id), 
	CONSTRAINT estadocamara CHECK (estado IN ('en_linea', 'desconectada'))
);

CREATE TABLE notificaciones (
	id SERIAL NOT NULL, 
	usuario_id INTEGER, 
	titulo VARCHAR(120) NOT NULL, 
	mensaje TEXT NOT NULL, 
	leida BOOLEAN NOT NULL, 
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

CREATE INDEX ix_notificaciones_usuario_id ON notificaciones (usuario_id);

CREATE TABLE vehiculos (
	id SERIAL NOT NULL, 
	usuario_id INTEGER NOT NULL, 
	placa VARCHAR(20), 
	marca VARCHAR(60) NOT NULL, 
	modelo VARCHAR(60) NOT NULL, 
	color VARCHAR(40) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE, 
	UNIQUE (placa)
);

CREATE INDEX ix_vehiculos_usuario_id ON vehiculos (usuario_id);

CREATE TABLE colgantes (
	id SERIAL NOT NULL, 
	codigo VARCHAR(40) NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	vehiculo_id INTEGER, 
	activo BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT tipocolgante CHECK (tipo IN ('estudiante', 'docente', 'directivo', 'administrativo', 'visitante')), 
	UNIQUE (vehiculo_id), 
	FOREIGN KEY(vehiculo_id) REFERENCES vehiculos (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX ix_colgantes_codigo ON colgantes (codigo);

CREATE TABLE espacios (
	id SERIAL NOT NULL, 
	numero VARCHAR(20) NOT NULL, 
	zona_id INTEGER NOT NULL, 
	camara_id INTEGER, 
	tipo VARCHAR(30) NOT NULL, 
	estado VARCHAR(30) NOT NULL, 
	monitoreado BOOLEAN NOT NULL, 
	estado_desde TIMESTAMP WITH TIME ZONE, 
	inicio_observado BOOLEAN NOT NULL, 
	objeto VARCHAR(40), 
	roi JSON, 
	usuario_asignado_id INTEGER, 
	colgante_actual_id INTEGER, 
	actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (zona_id, numero), 
	FOREIGN KEY(zona_id) REFERENCES zonas (id), 
	FOREIGN KEY(camara_id) REFERENCES camaras (id) ON DELETE SET NULL, 
	CONSTRAINT tipoespacio CHECK (tipo IN ('general', 'discapacidad', 'directivo', 'visitante', 'motocicleta')), 
	CONSTRAINT estadoespacio CHECK (estado IN ('libre', 'ocupado', 'reservado', 'fuera_de_servicio', 'obstruido')), 
	FOREIGN KEY(usuario_asignado_id) REFERENCES usuarios (id) ON DELETE SET NULL, 
	FOREIGN KEY(colgante_actual_id) REFERENCES colgantes (id) ON DELETE SET NULL
);

CREATE INDEX ix_espacios_zona_estado ON espacios (zona_id, estado);

CREATE TABLE eventos (
	id SERIAL NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	descripcion TEXT NOT NULL, 
	espacio_id INTEGER, 
	camara_id INTEGER, 
	colgante_id INTEGER, 
	confianza FLOAT, 
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT tipoevento CHECK (tipo IN ('entrada', 'salida', 'cambio_ocupacion', 'error_deteccion', 'camara_desconectada', 'camara_restablecida', 'obstruccion', 'obstruccion_retirada')), 
	FOREIGN KEY(espacio_id) REFERENCES espacios (id) ON DELETE SET NULL, 
	FOREIGN KEY(camara_id) REFERENCES camaras (id) ON DELETE SET NULL, 
	FOREIGN KEY(colgante_id) REFERENCES colgantes (id) ON DELETE SET NULL
);

CREATE INDEX ix_eventos_creado_en ON eventos (creado_en);

CREATE INDEX ix_eventos_tipo_fecha ON eventos (tipo, creado_en);
