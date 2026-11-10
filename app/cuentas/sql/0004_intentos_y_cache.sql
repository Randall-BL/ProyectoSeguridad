-- Intentos fallidos y caché compartida (tarea 3.7).
GRANT SELECT, INSERT, UPDATE, DELETE ON cuentas_intentosacceso TO va_app;

-- La tabla de la caché de Django, la misma que crea «manage.py createcachetable», escrita aquí para
-- dar los permisos en la misma migración. Guarda los límites de intentos de allauth y los códigos
-- TOTP ya usados, compartidos entre las instancias de Cloud Run. Django guarda los valores con
-- pickle: solo va_app escribe en ella, y nada de lo que guarda viene sin pasar por la aplicación.
CREATE TABLE IF NOT EXISTS cache_compartida (
    cache_key varchar(255) NOT NULL PRIMARY KEY,
    value text NOT NULL,
    expires timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS cache_compartida_expires ON cache_compartida (expires);
REVOKE ALL ON cache_compartida FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON cache_compartida TO va_app;
