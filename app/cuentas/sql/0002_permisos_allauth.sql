-- Permisos de va_app sobre las tablas de django-allauth (tarea 3.3).
-- Los correos no se usan para entrar ni para recuperar la cuenta: solo se leen y se mantienen.
GRANT SELECT, INSERT, UPDATE ON account_emailaddress TO va_app;
GRANT SELECT ON account_emailconfirmation TO va_app;

-- Segundos factores. allauth borra y vuelve a crear la fila de códigos de recuperación cuando la
-- persona los regenera; ese es el único borrado que se permite. El TOTP no se quita desde la
-- aplicación (POL-AU-05); restablecerlo es un trámite de ADM y GER (POL-AU-10).
GRANT SELECT, INSERT, UPDATE, DELETE ON mfa_authenticator TO va_app;
ALTER TABLE mfa_authenticator ENABLE ROW LEVEL SECURITY;
CREATE POLICY va_app_lee ON mfa_authenticator FOR SELECT TO va_app USING (true);
CREATE POLICY va_app_inserta ON mfa_authenticator FOR INSERT TO va_app WITH CHECK (true);
CREATE POLICY va_app_cambia ON mfa_authenticator FOR UPDATE TO va_app USING (true) WITH CHECK (true);
CREATE POLICY va_app_borra_codigos ON mfa_authenticator FOR DELETE TO va_app
    USING (type = 'recovery_codes');

DO $$
DECLARE
    tabla text;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['account_emailaddress', 'mfa_authenticator'] LOOP
        IF pg_get_serial_sequence(tabla, 'id') IS NOT NULL THEN
            EXECUTE format('GRANT USAGE ON SEQUENCE %s TO va_app', pg_get_serial_sequence(tabla, 'id'));
        END IF;
    END LOOP;
END
$$;
