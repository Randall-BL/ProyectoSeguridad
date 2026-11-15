CREATE OR REPLACE FUNCTION va_hechos_sujeto(p_usuario uuid, p_rol text, p_finca uuid) RETURNS jsonb
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
