-- Seguridad por fila (tarea 2.5): el segundo candado de C1 y C5. La aplicación indica en cada
-- transacción quién pide y con qué rol (SET LOCAL app.usuario / app.rol, desde la sesión del
-- servidor). Con eso la base filtra sola: un técnico solo ve las filas de sus fincas asignadas
-- (C1), un dueño solo las de su titular (C5), y AUD y DUE no escriben nada. Sin rol, nada.
-- El dueño de las tablas (migraciones) no pasa por estas políticas.

CREATE FUNCTION va_usuario() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.usuario', true), '')::uuid
$$;
CREATE FUNCTION va_rol() RETURNS text LANGUAGE sql STABLE AS $$
    SELECT coalesce(current_setting('app.rol', true), '')
$$;
-- Puede escribir: hay rol y no es de solo lectura.
CREATE FUNCTION va_escribe() RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT va_rol() NOT IN ('', 'AUD', 'DUE')
$$;

-- Las comprobaciones de alcance corren como dueño (SECURITY DEFINER) para no depender de las
-- políticas de las tablas que consultan.

-- C1: asignación vigente a la finca (ordinaria con el período abierto; temporal hasta su fecha de
-- fin) o técnico responsable de una enmienda en trámite sobre ella.
CREATE FUNCTION va_tec_finca(p_finca uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM negocio_asignacion a JOIN negocio_periodo p ON p.id = a.periodo_id
        WHERE a.tecnico_id = va_usuario() AND a.finca_id = p_finca AND a.terminada_en IS NULL
          AND ((a.tipo = 'ordinaria' AND p.estado = 'abierto')
            OR (a.tipo = 'temporal' AND current_date BETWEEN a.desde AND a.hasta))
    ) OR EXISTS (
        SELECT 1 FROM negocio_enmienda e
        JOIN negocio_medicion m ON m.id = e.medicion_id
        JOIN negocio_parcela pa ON pa.id = m.parcela_id
        WHERE e.responsable_id = va_usuario() AND pa.finca_id = p_finca
          AND e.estado = 'solicitada'
    )
$$;
CREATE FUNCTION va_tec_parcela(p_parcela uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT va_tec_finca((SELECT finca_id FROM negocio_parcela WHERE id = p_parcela))
$$;
-- Además, el técnico siempre lee las mediciones que él mismo registró (C1).
CREATE FUNCTION va_tec_medicion(p_medicion uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT va_tec_parcela((SELECT parcela_id FROM negocio_medicion WHERE id = p_medicion))
        OR EXISTS (SELECT 1 FROM negocio_versionmedicion
                   WHERE medicion_id = p_medicion AND autor_id = va_usuario())
$$;
CREATE FUNCTION va_tec_titular(p_titular uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (SELECT 1 FROM negocio_finca WHERE titular_id = p_titular AND va_tec_finca(id))
$$;

-- C5: relación vigente con el titular (es el titular o un representante autorizado).
CREATE FUNCTION va_due_titular(p_titular uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM negocio_representacion
        WHERE usuario_id = va_usuario() AND titular_id = p_titular
          AND desde <= current_date AND (hasta IS NULL OR hasta >= current_date)
    )
$$;
CREATE FUNCTION va_due_finca(p_finca uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT va_due_titular((SELECT titular_id FROM negocio_finca WHERE id = p_finca))
$$;
CREATE FUNCTION va_due_parcela(p_parcela uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT va_due_finca((SELECT finca_id FROM negocio_parcela WHERE id = p_parcela))
$$;
-- El dueño ve una medición solo cuando está aprobada (P-16).
CREATE FUNCTION va_due_medicion(p_medicion uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (SELECT 1 FROM negocio_medicion
                   WHERE id = p_medicion AND estado = 'aprobada' AND va_due_parcela(parcela_id))
$$;

-- Políticas. Para cada tabla: qué filas se ven según el rol, y quién puede escribir.
DO $$
DECLARE
    regla record;
BEGIN
    FOR regla IN SELECT * FROM (VALUES
        ('negocio_titular',         'va_tec_titular(id)',               'va_due_titular(id)'),
        ('negocio_finca',           'va_tec_finca(id)',                 'va_due_titular(titular_id)'),
        ('negocio_parcela',         'va_tec_finca(finca_id)',           'va_due_finca(finca_id)'),
        ('negocio_datospersonales', 'va_tec_titular(titular_id)',       'va_due_titular(titular_id)'),
        ('negocio_asignacion',      'tecnico_id = va_usuario()',        'va_due_finca(finca_id)'),
        ('negocio_medicion',        'va_tec_medicion(id)',              'estado = ''aprobada'' AND va_due_parcela(parcela_id)'),
        ('negocio_versionmedicion', 'va_tec_medicion(medicion_id)',     'va_due_medicion(medicion_id) AND NOT es_propuesta'),
        ('negocio_enmienda',        'responsable_id = va_usuario() OR va_tec_medicion(medicion_id)', 'va_due_medicion(medicion_id)'),
        ('negocio_certificado',     'false',                            'va_due_parcela(parcela_id)')
    ) AS r(tabla, alcance_tec, alcance_due) LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', regla.tabla);
        EXECUTE format(
            'CREATE POLICY va_app_lee ON %I FOR SELECT TO va_app USING (CASE va_rol() '
            'WHEN '''' THEN false WHEN ''TEC'' THEN (%s) WHEN ''DUE'' THEN (%s) ELSE true END)',
            regla.tabla, regla.alcance_tec, regla.alcance_due);
        EXECUTE format(
            'CREATE POLICY va_app_inserta ON %I FOR INSERT TO va_app WITH CHECK (va_escribe() '
            'AND (va_rol() <> ''TEC'' OR (%s)))',
            regla.tabla, regla.alcance_tec);
        EXECUTE format(
            'CREATE POLICY va_app_cambia ON %I FOR UPDATE TO va_app '
            'USING (va_escribe() AND (va_rol() <> ''TEC'' OR (%s))) WITH CHECK (va_escribe())',
            regla.tabla, regla.alcance_tec);
        -- Los demás componentes no actúan en nombre de una persona: su límite son sus permisos.
        EXECUTE format('CREATE POLICY otros_componentes ON %I TO va_emision, va_trabajos USING (true)',
                       regla.tabla);
    END LOOP;
END
$$;

-- Tablas sin alcance por finca: las lee cualquiera con rol, y AUD y DUE no escriben en ellas.
DO $$
DECLARE
    tabla text;
BEGIN
    FOREACH tabla IN ARRAY ARRAY[
        'negocio_representacion', 'negocio_vinculo', 'negocio_propuestacatalogo', 'negocio_periodo',
        'negocio_propuestaperiodo', 'negocio_alerta', 'cuentas_propuestarol', 'cuentas_declaracion'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tabla);
        EXECUTE format('CREATE POLICY va_app_lee ON %I FOR SELECT TO va_app USING (va_rol() <> '''')', tabla);
        EXECUTE format('CREATE POLICY va_app_inserta ON %I FOR INSERT TO va_app WITH CHECK (va_escribe())', tabla);
        EXECUTE format('CREATE POLICY va_app_cambia ON %I FOR UPDATE TO va_app USING (va_escribe()) '
                       'WITH CHECK (va_escribe())', tabla);
        EXECUTE format('CREATE POLICY otros_componentes ON %I TO va_emision, va_trabajos USING (true)', tabla);
    END LOOP;
END
$$;

-- La bitácora la leen solo GER y AUD (POL-BT-05); la escritura va por bitacora_anexar().
ALTER TABLE bitacora_registro ENABLE ROW LEVEL SECURITY;
CREATE POLICY va_app_lee ON bitacora_registro FOR SELECT TO va_app USING (va_rol() IN ('GER', 'AUD'));
CREATE POLICY trabajos_lee ON bitacora_registro FOR SELECT TO va_trabajos USING (true);
