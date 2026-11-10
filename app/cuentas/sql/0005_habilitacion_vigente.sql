-- El rol activo (tarea 3.8) se decide antes de que la sesión tenga rol, y cuentas_propuestarol solo
-- se lee con un rol puesto (seguridad por fila). Esta función responde lo único que hace falta en
-- ese momento: si la persona tiene una habilitación de técnico aprobada y vigente hoy, en la hora
-- de Costa Rica.
CREATE FUNCTION va_habilitacion_vigente(p_usuario uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM cuentas_propuestarol
        WHERE usuario_id = p_usuario AND es_habilitacion AND rol = 'TEC' AND estado = 'aprobada'
          AND fin_habilitacion >= (now() AT TIME ZONE 'America/Costa_Rica')::date
    )
$$;
REVOKE EXECUTE ON FUNCTION va_habilitacion_vigente(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION va_habilitacion_vigente(uuid) TO va_app;
