-- Bitácora: solo se agrega, va encadenada con SHA-256 y nadie la modifica, tampoco el dueño de
-- la tabla (POL-BT-01 a 06; Arquitectura §4.5; Schneier y Kelsey, 1999).

CREATE TABLE bitacora_registro (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instante       timestamptz NOT NULL,
    usuario_id     uuid,
    rol            text NOT NULL,
    accion         text NOT NULL,
    objeto_tipo    text NOT NULL,
    objeto_id      text NOT NULL,
    objeto_version text NOT NULL,
    resultado      text NOT NULL CHECK (resultado IN ('concedido', 'denegado', 'restringido', 'error')),
    regla          text NOT NULL,
    origen         text NOT NULL,
    sesion         text NOT NULL,
    huella_antes   text NOT NULL,
    huella_despues text NOT NULL,
    huella_previa  text NOT NULL,
    huella         text NOT NULL UNIQUE
);
CREATE INDEX bitacora_registro_usuario_instante ON bitacora_registro (usuario_id, instante);

-- Lo que se encadena de cada registro, en orden fijo y sin ambigüedad: un arreglo JSON.
CREATE FUNCTION bitacora_contenido(
    huella_previa text, instante timestamptz, usuario_id uuid, rol text, accion text,
    objeto_tipo text, objeto_id text, objeto_version text, resultado text, regla text,
    origen text, sesion text, huella_antes text, huella_despues text
) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT jsonb_build_array(
        $1, to_char($2 AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
    )::text
$$;

-- La única forma de escribir. Corre con los permisos del dueño (SECURITY DEFINER): quien la llama
-- no necesita, ni tiene, permiso de INSERT sobre la tabla.
CREATE FUNCTION bitacora_anexar(
    p_usuario uuid, p_rol text, p_accion text, p_objeto_tipo text, p_objeto_id text,
    p_objeto_version text, p_resultado text, p_regla text, p_origen text, p_sesion text,
    p_huella_antes text, p_huella_despues text
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_instante timestamptz := clock_timestamp();
    v_previa   text;
    v_huella   text;
    v_id       bigint;
BEGIN
    -- Un registro a la vez hasta el fin de la transacción: dos inserciones simultáneas no pueden
    -- tomar la misma huella previa.
    PERFORM pg_advisory_xact_lock(hashtext('bitacora_registro'));
    SELECT huella INTO v_previa FROM bitacora_registro ORDER BY id DESC LIMIT 1;
    v_previa := coalesce(v_previa, repeat('0', 64));

    p_rol := coalesce(p_rol, '');            p_objeto_tipo := coalesce(p_objeto_tipo, '');
    p_objeto_id := coalesce(p_objeto_id, ''); p_objeto_version := coalesce(p_objeto_version, '');
    p_regla := coalesce(p_regla, '');        p_origen := coalesce(p_origen, '');
    p_sesion := coalesce(p_sesion, '');      p_huella_antes := coalesce(p_huella_antes, '');
    p_huella_despues := coalesce(p_huella_despues, '');

    v_huella := encode(sha256(convert_to(bitacora_contenido(
        v_previa, v_instante, p_usuario, p_rol, p_accion, p_objeto_tipo, p_objeto_id,
        p_objeto_version, p_resultado, p_regla, p_origen, p_sesion, p_huella_antes,
        p_huella_despues), 'UTF8')), 'hex');

    INSERT INTO bitacora_registro (
        instante, usuario_id, rol, accion, objeto_tipo, objeto_id, objeto_version, resultado,
        regla, origen, sesion, huella_antes, huella_despues, huella_previa, huella
    ) VALUES (
        v_instante, p_usuario, p_rol, p_accion, p_objeto_tipo, p_objeto_id, p_objeto_version,
        p_resultado, p_regla, p_origen, p_sesion, p_huella_antes, p_huella_despues, v_previa,
        v_huella
    ) RETURNING id INTO v_id;
    RETURN v_id;
END
$$;

-- Recalcula toda la cadena. Devuelve NULL si está íntegra o el primer registro que no coincide.
-- Quitar el último registro no se ve aquí: para eso está el testigo externo (tarea 7.5).
CREATE FUNCTION bitacora_verificar() RETURNS bigint LANGUAGE plpgsql STABLE AS $$
DECLARE
    r        bitacora_registro;
    v_previa text := repeat('0', 64);
BEGIN
    FOR r IN SELECT * FROM bitacora_registro ORDER BY id LOOP
        IF r.huella_previa <> v_previa OR r.huella <> encode(sha256(convert_to(bitacora_contenido(
               r.huella_previa, r.instante, r.usuario_id, r.rol, r.accion, r.objeto_tipo,
               r.objeto_id, r.objeto_version, r.resultado, r.regla, r.origen, r.sesion,
               r.huella_antes, r.huella_despues), 'UTF8')), 'hex') THEN
            RETURN r.id;
        END IF;
        v_previa := r.huella;
    END LOOP;
    RETURN NULL;
END
$$;

-- Nadie modifica ni borra: ni la aplicación, ni la Gerencia, ni el dueño de la tabla.
CREATE FUNCTION bitacora_solo_agregar() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La bitácora solo admite inserciones (POL-BT-03)';
END
$$;
CREATE TRIGGER bitacora_sin_cambios BEFORE UPDATE OR DELETE ON bitacora_registro
    FOR EACH ROW EXECUTE FUNCTION bitacora_solo_agregar();
CREATE TRIGGER bitacora_sin_vaciar BEFORE TRUNCATE ON bitacora_registro
    FOR EACH STATEMENT EXECUTE FUNCTION bitacora_solo_agregar();

-- Permisos: leer (GER y AUD leen por medio de la aplicación) y anexar por la función.
REVOKE ALL ON bitacora_registro FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION bitacora_anexar(uuid, text, text, text, text, text, text, text, text, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION bitacora_anexar(uuid, text, text, text, text, text, text, text, text, text, text, text)
    TO va_app, va_emision, va_trabajos;
GRANT SELECT ON bitacora_registro TO va_app, va_trabajos;
