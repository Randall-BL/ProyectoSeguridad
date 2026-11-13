-- Testigo externo (7.5): solo se agregan sellos. Los escribe va_trabajos y los lee la aplicación
-- para GER y AUD; nadie los cambia ni los borra.
CREATE TRIGGER testigo_sin_cambios BEFORE UPDATE OR DELETE ON bitacora_testigo
    FOR EACH ROW EXECUTE FUNCTION bitacora_solo_agregar();
CREATE TRIGGER testigo_sin_vaciar BEFORE TRUNCATE ON bitacora_testigo
    FOR EACH STATEMENT EXECUTE FUNCTION bitacora_solo_agregar();
REVOKE ALL ON bitacora_testigo FROM PUBLIC;
GRANT SELECT, INSERT ON bitacora_testigo TO va_trabajos;
GRANT SELECT ON bitacora_testigo TO va_app;
DO $$
BEGIN
    EXECUTE format('GRANT USAGE ON SEQUENCE %s TO va_trabajos', pg_get_serial_sequence('bitacora_testigo', 'id'));
END
$$;
