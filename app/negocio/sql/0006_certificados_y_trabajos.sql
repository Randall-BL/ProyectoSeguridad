-- Fases 6 y 7: el segundo candado de C4 sobre los certificados, la comprobación pública por código
-- (C20) y los permisos de los trabajos programados (7.2 y 7.4).

-- C4: un certificado sale solo de una medición aprobada, con las toneladas, la parcela y el período
-- de su versión vigente, y nace vigente. Después lo único que puede pasarle es quedar revocado, una
-- vez. Lo comprueba el servicio de emisión y, además, la base: ni con el usuario de emisión se
-- inserta un certificado que no corresponda a lo aprobado.
CREATE FUNCTION va_certificado_c4() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    m record;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.estado <> 'vigente' OR NEW.estado <> 'revocado' OR NEW.revocado_en IS NULL THEN
            RAISE EXCEPTION 'C4: un certificado solo pasa de vigente a revocado';
        END IF;
        RETURN NEW;
    END IF;
    SELECT md.estado, md.parcela_id, md.periodo_id, v.toneladas_co2 INTO m
    FROM negocio_medicion md JOIN negocio_versionmedicion v ON v.id = md.version_vigente_id
    WHERE md.id = NEW.medicion_id;
    IF NOT FOUND OR m.estado <> 'aprobada' THEN
        RAISE EXCEPTION 'C4: solo se certifica una medición aprobada';
    END IF;
    IF NEW.parcela_id <> m.parcela_id OR NEW.periodo_id <> m.periodo_id
       OR NEW.toneladas_co2 <> m.toneladas_co2 THEN
        RAISE EXCEPTION 'C4: el certificado no corresponde a la medición aprobada';
    END IF;
    IF NEW.estado <> 'vigente' OR NEW.revocado_en IS NOT NULL THEN
        RAISE EXCEPTION 'C4: un certificado nace vigente';
    END IF;
    IF NEW.contenido->>'codigo' IS DISTINCT FROM NEW.codigo
       OR NEW.contenido->>'clave_id' IS DISTINCT FROM NEW.clave_id
       OR (NEW.contenido->>'toneladas_co2')::numeric IS DISTINCT FROM NEW.toneladas_co2 THEN
        RAISE EXCEPTION 'C4: el contenido firmado no coincide con el certificado';
    END IF;
    IF NEW.reemplaza_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM negocio_certificado
        WHERE id = NEW.reemplaza_id AND estado = 'revocado'
          AND parcela_id = NEW.parcela_id AND periodo_id = NEW.periodo_id) THEN
        RAISE EXCEPTION 'C4: solo se reemplaza un certificado revocado de la misma parcela y período';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER regla_certificado BEFORE INSERT OR UPDATE ON negocio_certificado
    FOR EACH ROW EXECUTE FUNCTION va_certificado_c4();

-- C20: el público consulta un certificado por su código exacto. Sin listados ni búsquedas (no hay
-- LIKE: o el código es exacto o no hay respuesta) y sin datos del titular. va_publico no tiene
-- permiso sobre ninguna tabla: solo puede llamar a esta función.
CREATE FUNCTION va_comprobar(p_codigo text)
RETURNS TABLE (codigo text, estado text, toneladas_co2 numeric, periodo text, emitido_en timestamptz,
               revocado_en timestamptz, reemplazado_por text, contenido jsonb, firma text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT c.codigo, c.estado, c.toneladas_co2, p.nombre, c.emitido_en, c.revocado_en, r.codigo,
           c.contenido, c.firma
    FROM negocio_certificado c
    JOIN negocio_periodo p ON p.id = c.periodo_id
    LEFT JOIN negocio_certificado r ON r.reemplaza_id = c.id
    WHERE c.codigo = p_codigo
$$;
REVOKE EXECUTE ON FUNCTION va_comprobar(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION va_comprobar(text) TO va_publico;

-- va_trabajos (7.2): vence asignaciones temporales, da de baja cuentas (ventana de auditor vencida o
-- 45 días sin uso, POL-CA-06) y cierra sus sesiones. Borrar sesiones es lo único que borra.
GRANT SELECT (date_joined, username, supervisor_id) ON cuentas_usuario TO va_trabajos;
GRANT SELECT (usuario_id, expire_date), DELETE ON cuentas_sesion TO va_trabajos;
-- 7.4: marca las alertas que SUP no resolvió en dos días hábiles (C15).
GRANT UPDATE (escalada_en) ON negocio_alerta TO va_trabajos;
GRANT EXECUTE ON FUNCTION va_dias_habiles(date, date) TO va_trabajos;
