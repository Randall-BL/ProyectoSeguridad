-- Usuario con el que se conecta la aplicación. No es dueño de ninguna tabla: recibe solo los
-- permisos que le da la matriz (tarea 2.3). La clave la pone infra/crear-secretos.sh, que la
-- genera y la manda directo a Secret Manager sin mostrarla.
-- CREATE ROLE ya deja NOSUPERUSER, NOCREATEDB, NOCREATEROLE y NOBYPASSRLS; en Neon el dueño de la
-- base no es superusuario y no puede escribir esos atributos, así que se comprueban al final.
\set ON_ERROR_STOP on
SELECT 'CREATE ROLE va_app LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'va_app') \gexec
ALTER ROLE va_app WITH LOGIN PASSWORD :'clave';
GRANT CONNECT ON DATABASE verdeazul TO va_app;

DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'va_app'
             AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolreplication)) THEN
    RAISE EXCEPTION 'va_app tiene atributos de más';
  END IF;
  IF pg_has_role('va_app', 'neon_superuser', 'MEMBER') THEN
    RAISE EXCEPTION 'va_app no debe pertenecer a neon_superuser';
  END IF;
END $$;
