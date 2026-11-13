-- Reglas de la matriz que también se pueden expresar en la base (tarea 2.6). Son el segundo
-- candado: OPA decide primero y estos disparadores vuelven a revisar dentro de la transacción,
-- así que dos personas que actúan a la vez no dejan la base en un estado que las reglas prohíben.
-- Pueden negar, nunca conceder.

-- C2 y C14: no se registra ni se envía con el período cerrado, y la fecha de medición declarada
-- cae dentro del período. La versión propuesta de una enmienda sí se registra después del cierre.
CREATE FUNCTION va_regla_periodo_abierto() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_periodo negocio_periodo;
BEGIN
    IF TG_TABLE_NAME = 'negocio_versionmedicion' THEN
        SELECT p.* INTO v_periodo FROM negocio_periodo p
            JOIN negocio_medicion m ON m.periodo_id = p.id WHERE m.id = NEW.medicion_id;
        IF NEW.fecha_medicion < v_periodo.inicio OR NEW.fecha_medicion > v_periodo.fin_medicion THEN
            RAISE EXCEPTION 'C2: la fecha de medición está fuera del período %', v_periodo.nombre;
        END IF;
        IF NEW.es_propuesta THEN
            RETURN NEW;
        END IF;
    ELSE
        SELECT * INTO v_periodo FROM negocio_periodo WHERE id = NEW.periodo_id;
        IF TG_OP = 'UPDATE' AND NOT (NEW.estado = 'enviada' AND OLD.estado IS DISTINCT FROM 'enviada') THEN
            RETURN NEW;
        END IF;
    END IF;
    IF v_periodo.estado <> 'abierto' THEN
        RAISE EXCEPTION 'C2/C14: el período % no está abierto', v_periodo.nombre;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER regla_periodo_abierto BEFORE INSERT ON negocio_versionmedicion
    FOR EACH ROW EXECUTE FUNCTION va_regla_periodo_abierto();
CREATE TRIGGER regla_periodo_abierto BEFORE INSERT OR UPDATE OF estado ON negocio_medicion
    FOR EACH ROW EXECUTE FUNCTION va_regla_periodo_abierto();

-- C3, C8 y C10 (H4 y K-2): quien decide no figura entre los autores de ninguna versión de la
-- medición, comparando el id de usuario, ni en un paso anterior de la enmienda.
CREATE FUNCTION va_autores(p_medicion uuid) RETURNS SETOF uuid LANGUAGE sql STABLE AS $$
    SELECT autor_id FROM negocio_versionmedicion WHERE medicion_id = p_medicion
$$;

CREATE FUNCTION va_regla_quien_registro_no_aprueba() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.estado = 'aprobada' AND OLD.estado IS DISTINCT FROM 'aprobada' THEN
        IF OLD.estado <> 'enviada' THEN
            RAISE EXCEPTION 'C3: solo se aprueba una medición enviada';
        END IF;
        IF NEW.aprobada_por_id IS NULL OR NEW.aprobada_por_id IN (SELECT va_autores(NEW.id)) THEN
            RAISE EXCEPTION 'C3: quien registró o modificó la medición no la aprueba';
        END IF;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER regla_quien_registro_no_aprueba BEFORE UPDATE OF estado ON negocio_medicion
    FOR EACH ROW EXECUTE FUNCTION va_regla_quien_registro_no_aprueba();

CREATE FUNCTION va_regla_enmienda_independiente() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_aprobador uuid;
BEGIN
    IF NEW.revisada_por_id IS NOT NULL AND OLD.revisada_por_id IS NULL THEN
        IF NEW.revisada_por_id IN (SELECT va_autores(NEW.medicion_id))
           OR NEW.revisada_por_id = NEW.solicitada_por_id THEN
            RAISE EXCEPTION 'C10: la revisión técnica la da alguien que no es autor ni solicitante';
        END IF;
        SELECT aprobada_por_id INTO v_aprobador FROM negocio_medicion WHERE id = NEW.medicion_id;
        IF NEW.material AND NEW.revisada_por_id = v_aprobador THEN
            RAISE EXCEPTION 'C10: en una enmienda material no revisa quien aprobó la versión corregida';
        END IF;
    END IF;
    IF NEW.autorizada_por_id IS NOT NULL AND OLD.autorizada_por_id IS NULL THEN
        IF NEW.dictamen_favorable IS NOT TRUE THEN
            RAISE EXCEPTION 'C8: no se autoriza sin dictamen técnico favorable';
        END IF;
        IF NEW.autorizada_por_id IN (SELECT va_autores(NEW.medicion_id))
           OR NEW.autorizada_por_id IN (NEW.solicitada_por_id, NEW.revisada_por_id) THEN
            RAISE EXCEPTION 'C8: autoriza alguien que no solicitó, no revisó y no es autor';
        END IF;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER regla_enmienda_independiente BEFORE UPDATE ON negocio_enmienda
    FOR EACH ROW EXECUTE FUNCTION va_regla_enmienda_independiente();

-- C11 y P-21: el área sale de la geometría, y una parcela activa no se traslapa con otra activa
-- (salvo con la que reemplaza).
CREATE FUNCTION va_regla_parcela() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT ST_IsValid(NEW.geometria) THEN
        RAISE EXCEPTION 'C11: la geometría de la parcela no es válida';
    END IF;
    NEW.area_ha := round((ST_Area(NEW.geometria::geography) / 10000)::numeric, 4);
    IF NEW.activa AND EXISTS (
        SELECT 1 FROM negocio_parcela otra
        WHERE otra.activa AND otra.id <> NEW.id AND otra.id IS DISTINCT FROM NEW.reemplaza_id
          AND ST_Relate(otra.geometria, NEW.geometria, 'T********')
    ) THEN
        RAISE EXCEPTION 'C11: la parcela se traslapa con otra parcela activa';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER regla_parcela BEFORE INSERT OR UPDATE OF geometria, activa ON negocio_parcela
    FOR EACH ROW EXECUTE FUNCTION va_regla_parcela();

-- C11, C12 y C14: segunda firma. Quien aprueba no es quien propone, ni el titular de la cuenta.
ALTER TABLE negocio_propuestacatalogo ADD CONSTRAINT c11_aprueba_otra_persona
    CHECK (aprobada_por_id IS NULL OR aprobada_por_id <> propuesta_por_id);
ALTER TABLE negocio_propuestaperiodo ADD CONSTRAINT c14_aprueba_otra_persona
    CHECK (aprobada_por_id IS NULL OR aprobada_por_id <> registrada_por_id);
ALTER TABLE cuentas_propuestarol ADD CONSTRAINT c12_nadie_se_administra
    CHECK (aprobada_por_id IS NULL OR (aprobada_por_id <> propuesta_por_id AND aprobada_por_id <> usuario_id));
ALTER TABLE cuentas_propuestarol ADD CONSTRAINT c12_nadie_se_propone
    CHECK (propuesta_por_id <> usuario_id);

-- C19 y K-1: se asigna a quien tiene el rol TEC (propio o por habilitación vigente), la temporal
-- dura 15 días como máximo, y un técnico no pasa del máximo de asignaciones activas de su rol.
ALTER TABLE negocio_asignacion ADD CONSTRAINT c19_temporal_hasta_15_dias
    CHECK (tipo = 'ordinaria' OR hasta - desde <= 15);

CREATE FUNCTION va_regla_asignacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_maximo integer;
    v_activas integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM cuentas_usuario WHERE id = NEW.tecnico_id AND rol = 'TEC' AND is_active)
       AND NOT EXISTS (SELECT 1 FROM cuentas_propuestarol
                       WHERE usuario_id = NEW.tecnico_id AND es_habilitacion AND estado = 'aprobada'
                         AND fin_habilitacion >= current_date) THEN
        RAISE EXCEPTION 'C19: solo se asigna a quien tiene el rol TEC vigente';
    END IF;
    SELECT max_asignaciones_activas INTO v_maximo FROM negocio_parametrorol WHERE rol = 'TEC';
    IF v_maximo IS NOT NULL THEN
        SELECT count(*) INTO v_activas
        FROM negocio_asignacion a JOIN negocio_periodo p ON p.id = a.periodo_id
        WHERE a.tecnico_id = NEW.tecnico_id AND a.terminada_en IS NULL
          AND ((a.tipo = 'ordinaria' AND p.estado <> 'cerrado')
            OR (a.tipo = 'temporal' AND current_date <= a.hasta));
        IF v_activas >= v_maximo THEN
            RAISE EXCEPTION 'K-1: el técnico ya tiene % asignaciones activas (máximo %)', v_activas, v_maximo;
        END IF;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER regla_asignacion BEFORE INSERT ON negocio_asignacion
    FOR EACH ROW EXECUTE FUNCTION va_regla_asignacion();

-- C16: los datos personales de un titular con un certificado emitido en los últimos diez años no
-- se suprimen (POL-BT-04).
CREATE FUNCTION va_regla_supresion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.suprimido_en IS NOT NULL AND OLD.suprimido_en IS NULL AND EXISTS (
        SELECT 1 FROM negocio_certificado c
        JOIN negocio_parcela pa ON pa.id = c.parcela_id
        JOIN negocio_finca f ON f.id = pa.finca_id
        WHERE f.titular_id = NEW.titular_id AND c.emitido_en > now() - interval '10 years'
    ) THEN
        RAISE EXCEPTION 'C16: hay un certificado dentro del plazo de trazabilidad';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER regla_supresion BEFORE UPDATE OF suprimido_en ON negocio_datospersonales
    FOR EACH ROW EXECUTE FUNCTION va_regla_supresion();

-- Valores iniciales de los parámetros por rol (P-02, P-12, P-13, K-1); GER los cambia después.
INSERT INTO negocio_parametrorol (rol, h1_aviso, h1_verificacion, h1_restriccion, h3_fincas_hora,
                                  jornada_inicio, jornada_fin, dias_laborales, max_asignaciones_activas,
                                  actualizado_en)
SELECT rol, 40, 60, 80, 10, '06:00', '19:00', '12345', CASE WHEN rol = 'TEC' THEN 20 END, now()
FROM unnest(ARRAY['TEC', 'VER', 'SUP', 'GER', 'ADM', 'AUD', 'DUE']) AS rol
ON CONFLICT (rol) DO NOTHING;
