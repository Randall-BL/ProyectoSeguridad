-- Usuario de base con el que se conecta un componente: va_app (la aplicación), va_emision (el
-- servicio de emisión), va_publico (la comprobación pública) o va_trabajos (los trabajos
-- programados). Ninguno es dueño de tablas: reciben solo los permisos de las migraciones (2.3).
-- La clave la pone infra/crear-secretos.sh, que la genera y la manda directo a Secret Manager sin
-- mostrarla.  Uso: psql "$DUENO" -v rol=va_emision -v clave=... -f db/roles/servicio.sql
-- CREATE ROLE ya deja NOSUPERUSER, NOCREATEDB, NOCREATEROLE y NOBYPASSRLS; en Neon el dueño de la
-- base no es superusuario y no puede escribir esos atributos, así que se comprueban al final.
\set ON_ERROR_STOP on
SELECT set_config('va.rol', :'rol', false);

DO $$
BEGIN
  IF current_setting('va.rol') NOT IN ('va_app', 'va_emision', 'va_publico', 'va_trabajos') THEN
    RAISE EXCEPTION 'Rol desconocido: %', current_setting('va.rol');
  END IF;
END $$;

SELECT format('CREATE ROLE %I LOGIN', :'rol') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'rol') \gexec
ALTER ROLE :"rol" WITH LOGIN PASSWORD :'clave';
GRANT CONNECT ON DATABASE verdeazul TO :"rol";

DO $$
DECLARE
  v_rol text := current_setting('va.rol');
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = v_rol
             AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolreplication)) THEN
    RAISE EXCEPTION '% tiene atributos de más', v_rol;
  END IF;
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'neon_superuser')
     AND pg_has_role(v_rol, 'neon_superuser', 'MEMBER') THEN
    RAISE EXCEPTION '% no debe pertenecer a neon_superuser', v_rol;
  END IF;
END $$;
