-- 8.4 (RR-10): las dos copias de una regla no pueden divergir. La seguridad por fila de C1 y C5 y
-- el disparador de C19 y K-1 usaban current_date, que es la fecha de la zona de la sesión (UTC con
-- Django y en Neon), mientras que los hechos que recibe el motor usan va_hoy(), la fecha de Costa
-- Rica. Entre las 18:00 y la medianoche de Costa Rica ya es «mañana» en UTC: una asignación
-- temporal que vence hoy desaparecía seis horas antes en la base aunque el motor la concediera, y
-- una habilitación o una representación igual. Las tres pasan a va_hoy().

CREATE OR REPLACE FUNCTION va_tec_finca(p_finca uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM negocio_asignacion a JOIN negocio_periodo p ON p.id = a.periodo_id
        WHERE a.tecnico_id = va_usuario() AND a.finca_id = p_finca AND a.terminada_en IS NULL
          AND ((a.tipo = 'ordinaria' AND p.estado = 'abierto')
            OR (a.tipo = 'temporal' AND va_hoy() BETWEEN a.desde AND a.hasta))
    ) OR EXISTS (
        SELECT 1 FROM negocio_enmienda e
        JOIN negocio_medicion m ON m.id = e.medicion_id
        JOIN negocio_parcela pa ON pa.id = m.parcela_id
        WHERE e.responsable_id = va_usuario() AND pa.finca_id = p_finca
          AND e.estado = 'solicitada'
    )
$$;

CREATE OR REPLACE FUNCTION va_due_titular(p_titular uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM negocio_representacion
        WHERE usuario_id = va_usuario() AND titular_id = p_titular
          AND desde <= va_hoy() AND (hasta IS NULL OR hasta >= va_hoy())
    )
$$;

-- El disparador pregunta lo mismo que el hecho tecnico_es_tec del motor (va_es_tecnico) y cuenta
-- las activas igual que va_asignaciones_activas.
CREATE OR REPLACE FUNCTION va_regla_asignacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_maximo integer;
    v_activas integer;
BEGIN
    IF NOT va_es_tecnico(NEW.tecnico_id) THEN
        RAISE EXCEPTION 'C19: solo se asigna a quien tiene el rol TEC vigente';
    END IF;
    SELECT max_asignaciones_activas INTO v_maximo FROM negocio_parametrorol WHERE rol = 'TEC';
    IF v_maximo IS NOT NULL THEN
        v_activas := va_asignaciones_activas(NEW.tecnico_id);
        IF v_activas >= v_maximo THEN
            RAISE EXCEPTION 'K-1: el técnico ya tiene % asignaciones activas (máximo %)', v_activas, v_maximo;
        END IF;
    END IF;
    RETURN NEW;
END
$$;
