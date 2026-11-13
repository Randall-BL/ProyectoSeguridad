-- Hechos de los flujos de la fase 5: asignaciones (C19, K-1), enmiendas (C7 a C10), titulares y sus
-- datos personales (C1, C5, C16) y certificados (C5). Igual que 0001: los calcula la base con la
-- verdad de las filas, sin datos personales, y solo va_app los puede pedir.

-- Días hábiles (lunes a viernes) después de p_desde y hasta p_hasta, inclusive (C9, C15).
CREATE FUNCTION va_dias_habiles(p_desde date, p_hasta date) RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT count(*)::integer
    FROM generate_series(p_desde + 1, p_hasta, interval '1 day') AS d
    WHERE extract(isodow FROM d) < 6
$$;

-- Asignaciones activas de un técnico (K-1): las ordinarias de un período que no cerró y las
-- temporales que no vencieron. Es la misma cuenta que hace el disparador de asignaciones.
CREATE FUNCTION va_asignaciones_activas(p_tecnico uuid) RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT count(*)::integer
    FROM negocio_asignacion a JOIN negocio_periodo p ON p.id = a.periodo_id
    WHERE a.tecnico_id = p_tecnico AND a.terminada_en IS NULL
      AND ((a.tipo = 'ordinaria' AND p.estado <> 'cerrado')
        OR (a.tipo = 'temporal' AND va_hoy() <= a.hasta))
$$;

-- Tiene el rol TEC vigente: propio o por una habilitación aprobada que no ha vencido (C19).
CREATE FUNCTION va_es_tecnico(p_usuario uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (SELECT 1 FROM cuentas_usuario WHERE id = p_usuario AND rol = 'TEC' AND is_active)
        OR EXISTS (SELECT 1 FROM cuentas_propuestarol
                   WHERE usuario_id = p_usuario AND rol = 'TEC' AND es_habilitacion
                     AND estado = 'aprobada' AND fin_habilitacion >= va_hoy())
$$;

-- Una asignación existente, o una nueva para un técnico y una finca (C19 y C17 por el titular).
CREATE FUNCTION va_hechos_asignacion(p_tecnico uuid, p_finca uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
SELECT jsonb_build_object(
    'tipo', 'asignaciones', 'tecnico', p_tecnico, 'finca', f.id, 'titular', f.titular_id,
    'tecnico_es_tec', va_es_tecnico(p_tecnico),
    'activas_del_tecnico', va_asignaciones_activas(p_tecnico))
FROM negocio_finca f
WHERE f.id = p_finca
$$;

-- Una enmienda: sus pasos, quién dio cada uno, los días hábiles desde la solicitud y los hechos de
-- la medición que corrige (autores de todas las versiones, quién la aprobó).
CREATE FUNCTION va_hechos_enmienda(p_enmienda uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
SELECT jsonb_build_object(
    'tipo', 'enmiendas', 'id', e.id, 'finca', pa.finca_id, 'titular', f.titular_id,
    'estado', e.estado, 'solicitada_por', e.solicitada_por_id, 'responsable', e.responsable_id,
    'revisada_por', e.revisada_por_id, 'dictamen_favorable', e.dictamen_favorable,
    'material', coalesce(e.material, false),
    'dias_habiles_desde_solicitud',
        va_dias_habiles((e.solicitada_en AT TIME ZONE 'America/Costa_Rica')::date, va_hoy()),
    'medicion', jsonb_build_object(
        'estado', m.estado, 'periodo_estado', p.estado, 'responsable', m.creada_por_id,
        'aprobada_por', m.aprobada_por_id,
        'autores', coalesce((SELECT jsonb_agg(DISTINCT v.autor_id) FROM negocio_versionmedicion v
                             WHERE v.medicion_id = m.id), '[]'::jsonb)))
FROM negocio_enmienda e
JOIN negocio_medicion m ON m.id = e.medicion_id
JOIN negocio_parcela pa ON pa.id = m.parcela_id
JOIN negocio_finca f ON f.id = pa.finca_id
JOIN negocio_periodo p ON p.id = m.periodo_id
WHERE e.id = p_enmienda
$$;

-- Un titular y sus datos personales. Para C1, una de sus fincas asignadas a quien pregunta (si
-- tiene alguna); para C16, si hay un certificado emitido en los últimos diez años (POL-BT-04).
CREATE FUNCTION va_hechos_titular(p_titular uuid, p_usuario uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
SELECT jsonb_build_object(
    'tipo', 'datos_personales', 'id', t.id, 'titular', t.id,
    'finca', coalesce(
        (SELECT a.finca_id FROM negocio_asignacion a
         JOIN negocio_finca f ON f.id = a.finca_id JOIN negocio_periodo p ON p.id = a.periodo_id
         WHERE f.titular_id = t.id AND a.tecnico_id = p_usuario AND a.terminada_en IS NULL
           AND ((a.tipo = 'ordinaria' AND p.estado = 'abierto')
             OR (a.tipo = 'temporal' AND va_hoy() BETWEEN a.desde AND a.hasta))
         LIMIT 1),
        (SELECT f.id FROM negocio_finca f WHERE f.titular_id = t.id ORDER BY f.codigo LIMIT 1)),
    'obligacion_conservar', EXISTS (
        SELECT 1 FROM negocio_certificado c
        JOIN negocio_parcela pa ON pa.id = c.parcela_id
        JOIN negocio_finca f ON f.id = pa.finca_id
        WHERE f.titular_id = t.id AND c.emitido_en > now() - interval '10 years'))
FROM negocio_titular t
WHERE t.id = p_titular
$$;

-- Un certificado: su finca y su titular (C5), su estado y su código.
CREATE FUNCTION va_hechos_certificado(p_certificado uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
SELECT jsonb_build_object(
    'tipo', 'certificados', 'id', c.id, 'finca', pa.finca_id, 'titular', f.titular_id,
    'estado', c.estado, 'codigo', c.codigo)
FROM negocio_certificado c
JOIN negocio_parcela pa ON pa.id = c.parcela_id
JOIN negocio_finca f ON f.id = pa.finca_id
WHERE c.id = p_certificado
$$;

DO $$
DECLARE
    firma text;
BEGIN
    FOREACH firma IN ARRAY ARRAY[
        'va_asignaciones_activas(uuid)', 'va_es_tecnico(uuid)', 'va_hechos_asignacion(uuid, uuid)',
        'va_hechos_enmienda(uuid)', 'va_hechos_titular(uuid, uuid)', 'va_hechos_certificado(uuid)'
    ] LOOP
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', firma);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO va_app', firma);
    END LOOP;
END
$$;
