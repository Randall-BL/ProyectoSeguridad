-- Hechos para el motor de decisión (tarea 4.6). Los calcula la base con la verdad de sus filas, sin
-- pasar por la seguridad por fila de quien pregunta: el motor tiene que poder decir «C1» sobre una
-- finca que el técnico no ve. Devuelven identificadores, estados y fechas, nunca datos personales,
-- y solo va_app las puede ejecutar.

CREATE FUNCTION va_hoy() RETURNS date LANGUAGE sql STABLE AS $$
    SELECT (now() AT TIME ZONE 'America/Costa_Rica')::date
$$;

-- El sujeto: sus fincas con asignación vigente (C1), los titulares que representa (C5), los
-- titulares con los que declaró vínculo (C17), sus técnicos a cargo (C15), los umbrales de su rol
-- y su historial de lecturas (H1 a H3), y si la finca del objeto es nueva para él.
CREATE FUNCTION va_hechos_sujeto(p_usuario uuid, p_rol text, p_finca uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
WITH hoy AS (
    SELECT va_hoy() AS d, (now() AT TIME ZONE 'America/Costa_Rica') AS ahora
), parametro AS (
    SELECT * FROM negocio_parametrorol WHERE rol = p_rol
), lecturas AS (
    SELECT finca_id, instante, denegado FROM negocio_eventolectura
    WHERE usuario_id = p_usuario AND instante > now() - interval '90 days'
), recientes AS (
    SELECT DISTINCT finca_id FROM lecturas WHERE instante > now() - interval '60 minutes'
)
SELECT jsonb_build_object(
    'fincas_asignadas', coalesce((
        SELECT jsonb_agg(DISTINCT x.finca_id) FROM (
            SELECT a.finca_id
            FROM negocio_asignacion a JOIN negocio_periodo p ON p.id = a.periodo_id CROSS JOIN hoy
            WHERE a.tecnico_id = p_usuario AND a.terminada_en IS NULL
              AND ((a.tipo = 'ordinaria' AND p.estado = 'abierto')
                OR (a.tipo = 'temporal' AND hoy.d BETWEEN a.desde AND a.hasta))
            UNION
            SELECT pa.finca_id
            FROM negocio_enmienda e
            JOIN negocio_medicion m ON m.id = e.medicion_id
            JOIN negocio_parcela pa ON pa.id = m.parcela_id
            WHERE e.responsable_id = p_usuario AND e.estado = 'solicitada'
        ) x), '[]'::jsonb),
    'titulares_representados', coalesce((
        SELECT jsonb_agg(DISTINCT r.titular_id) FROM negocio_representacion r CROSS JOIN hoy
        WHERE r.usuario_id = p_usuario AND r.desde <= hoy.d AND (r.hasta IS NULL OR r.hasta >= hoy.d)
    ), '[]'::jsonb),
    'titulares_con_vinculo', coalesce((
        SELECT jsonb_agg(DISTINCT v.titular_id) FROM negocio_vinculo v
        WHERE v.usuario_id = p_usuario AND v.retirado_en IS NULL
    ), '[]'::jsonb),
    'tecnicos_a_cargo', coalesce((
        SELECT jsonb_agg(u.id) FROM cuentas_usuario u WHERE u.supervisor_id = p_usuario AND u.is_active
    ), '[]'::jsonb),
    'parametros', coalesce((
        SELECT jsonb_build_object(
            'h1_aviso', h1_aviso, 'h1_verificacion', h1_verificacion,
            'h1_restriccion', h1_restriccion, 'h3_fincas_hora', h3_fincas_hora)
        FROM parametro
    ), '{}'::jsonb) || jsonb_build_object('max_asignaciones_activas', (
        SELECT max_asignaciones_activas FROM negocio_parametrorol WHERE rol = 'TEC'
    )),
    'historial', jsonb_build_object(
        -- H1: fincas distintas en 24 horas; las denegadas cuentan doble.
        'fincas_24h', (
            SELECT count(DISTINCT finca_id) + count(DISTINCT finca_id) FILTER (WHERE denegado)
            FROM lecturas WHERE instante > now() - interval '24 hours'),
        'fincas_60min', (SELECT count(*) FROM recientes),
        'finca_nueva', p_finca IS NOT NULL AND NOT EXISTS (SELECT 1 FROM lecturas WHERE finca_id = p_finca),
        -- H3: la mayoría de las fincas de la última hora no las había consultado en 90 días.
        'mayoria_nuevas_90d', coalesce((
            SELECT 2 * count(*) FILTER (WHERE NOT EXISTS (
                       SELECT 1 FROM lecturas l WHERE l.finca_id = r.finca_id
                         AND l.instante <= now() - interval '60 minutes')) > count(*)
            FROM recientes r), false),
        -- H2: fuera de la jornada del rol (días laborales ISO, 1 = lunes).
        'fuera_de_jornada', coalesce((
            SELECT NOT (position(extract(isodow FROM hoy.ahora)::text IN parametro.dias_laborales) > 0
                        AND hoy.ahora::time BETWEEN parametro.jornada_inicio AND parametro.jornada_fin)
            FROM parametro CROSS JOIN hoy), false)
    ),
    'hoy', (SELECT d FROM hoy)
)
$$;

-- Una medición: su finca y titular, su estado, los autores de todas sus versiones (C3, K-2),
-- quién la aprobó, su período y la asignación vigente del sujeto en esa finca (C2).
CREATE FUNCTION va_hechos_medicion(p_medicion uuid, p_usuario uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
SELECT jsonb_build_object(
    'tipo', 'mediciones', 'id', m.id, 'finca', pa.finca_id, 'titular', f.titular_id,
    'estado', m.estado,
    'autores', coalesce((SELECT jsonb_agg(DISTINCT v.autor_id) FROM negocio_versionmedicion v
                         WHERE v.medicion_id = m.id), '[]'::jsonb),
    'responsable', m.creada_por_id, 'aprobada_por', m.aprobada_por_id,
    'periodo_estado', p.estado, 'periodo_inicio', p.inicio, 'periodo_fin_medicion', p.fin_medicion,
    'asignacion_desde', a.desde, 'asignacion_hasta', a.hasta)
FROM negocio_medicion m
JOIN negocio_parcela pa ON pa.id = m.parcela_id
JOIN negocio_finca f ON f.id = pa.finca_id
JOIN negocio_periodo p ON p.id = m.periodo_id
LEFT JOIN LATERAL (
    SELECT desde, hasta FROM negocio_asignacion
    WHERE tecnico_id = p_usuario AND finca_id = pa.finca_id AND periodo_id = m.periodo_id
      AND terminada_en IS NULL
    ORDER BY desde DESC LIMIT 1
) a ON true
WHERE m.id = p_medicion
$$;

-- Una medición nueva en una parcela y un período (C2 al crear).
CREATE FUNCTION va_hechos_nueva_medicion(p_parcela uuid, p_periodo uuid, p_usuario uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
SELECT jsonb_build_object(
    'tipo', 'mediciones', 'finca', pa.finca_id, 'titular', f.titular_id,
    'periodo_estado', p.estado, 'periodo_inicio', p.inicio, 'periodo_fin_medicion', p.fin_medicion,
    'asignacion_desde', a.desde, 'asignacion_hasta', a.hasta)
FROM negocio_parcela pa
JOIN negocio_finca f ON f.id = pa.finca_id
CROSS JOIN negocio_periodo p
LEFT JOIN LATERAL (
    SELECT desde, hasta FROM negocio_asignacion
    WHERE tecnico_id = p_usuario AND finca_id = pa.finca_id AND periodo_id = p.id
      AND terminada_en IS NULL
    ORDER BY desde DESC LIMIT 1
) a ON true
WHERE pa.id = p_parcela AND p.id = p_periodo
$$;

-- Una finca: su titular, su estado y la propuesta de catálogo pendiente, si hay (C11).
CREATE FUNCTION va_hechos_finca(p_finca uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
SELECT jsonb_build_object(
    'tipo', 'fincas', 'id', f.id, 'finca', f.id, 'titular', f.titular_id, 'estado', f.estado,
    'propuesta', (SELECT jsonb_build_object('id', pc.id, 'estado', pc.estado, 'propuesta_por', pc.propuesta_por_id)
                  FROM negocio_propuestacatalogo pc
                  WHERE pc.finca_id = f.id AND pc.estado = 'propuesto'
                  ORDER BY pc.propuesta_en DESC LIMIT 1))
FROM negocio_finca f
WHERE f.id = p_finca
$$;

DO $$
DECLARE
    firma text;
BEGIN
    FOREACH firma IN ARRAY ARRAY[
        'va_hechos_sujeto(uuid, text, uuid)', 'va_hechos_medicion(uuid, uuid)',
        'va_hechos_nueva_medicion(uuid, uuid, uuid)', 'va_hechos_finca(uuid)'
    ] LOOP
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', firma);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO va_app', firma);
    END LOOP;
END
$$;
