-- Permisos de cada usuario de base sobre las tablas (tarea 2.3). Nada se concede a PUBLIC; lo que
-- no aparece aquí está denegado. Es el segundo candado: aunque la aplicación tuviera un error, la
-- base no deja borrar mediciones, cambiar una versión ya registrada ni emitir un certificado.

-- va_app: la aplicación, en nombre de las personas.
GRANT SELECT ON django_content_type, auth_permission, auth_group, auth_group_permissions,
                cuentas_usuario_groups, cuentas_usuario_user_permissions TO va_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON django_session TO va_app;

-- Cuentas: se crean y se desactivan, nunca se borran (POL-CA-05).
GRANT SELECT, INSERT, UPDATE ON cuentas_usuario, cuentas_propuestarol TO va_app;
GRANT SELECT, INSERT ON cuentas_declaracion TO va_app;

-- Negocio: sin DELETE en ninguna tabla. Los cambios son estados o versiones nuevas.
GRANT SELECT, INSERT, UPDATE ON
    negocio_titular, negocio_datospersonales, negocio_representacion, negocio_vinculo,
    negocio_finca, negocio_parcela, negocio_propuestacatalogo, negocio_periodo,
    negocio_propuestaperiodo, negocio_asignacion, negocio_medicion, negocio_enmienda,
    negocio_alerta
TO va_app;
-- Una versión de medición, una lectura registrada o una exportación no se modifican.
GRANT SELECT, INSERT ON negocio_versionmedicion, negocio_eventolectura, negocio_exportacionauditoria TO va_app;
GRANT SELECT, UPDATE ON negocio_parametrorol TO va_app;
-- Los certificados los emite solo va_emision (fila SIS, C4): la aplicación solo los lee.
GRANT SELECT ON negocio_certificado, negocio_certificado_enmiendas_anotadas TO va_app;

-- va_emision: el servicio de emisión. Lee lo necesario para emitir y escribe solo certificados.
GRANT SELECT ON negocio_medicion, negocio_versionmedicion, negocio_parcela, negocio_finca,
                negocio_periodo, negocio_enmienda, negocio_titular TO va_emision;
GRANT SELECT (id, first_name, last_name) ON cuentas_usuario TO va_emision;
GRANT SELECT (titular_id, nombre) ON negocio_datospersonales TO va_emision;
GRANT SELECT, INSERT ON negocio_certificado, negocio_certificado_enmiendas_anotadas TO va_emision;
GRANT UPDATE (estado, revocado_en) ON negocio_certificado TO va_emision;

-- va_trabajos: vencimientos y escalamiento de alertas (se completa en el sprint 4).
GRANT SELECT ON negocio_asignacion, negocio_alerta, cuentas_propuestarol TO va_trabajos;
GRANT SELECT (id, is_active, last_login, rol, vigente_hasta) ON cuentas_usuario TO va_trabajos;
GRANT UPDATE (terminada_en) ON negocio_asignacion TO va_trabajos;
GRANT UPDATE (is_active) ON cuentas_usuario TO va_trabajos;

-- Secuencias de las columnas autonuméricas en las que se inserta.
DO $$
DECLARE
    tabla text;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['negocio_eventolectura', 'negocio_certificado_enmiendas_anotadas'] LOOP
        EXECUTE format('GRANT USAGE ON SEQUENCE %s TO va_app, va_emision',
                       pg_get_serial_sequence(tabla, 'id'));
    END LOOP;
END
$$;
