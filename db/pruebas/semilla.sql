-- Comprueba que los datos de `manage.py sembrar` dejan listos los casos de la matriz (tarea 2.8).
-- Correr SOLO contra una base desechable recién sembrada (la de docker compose), con un usuario dueño:
--   docker compose exec -T db psql -U postgres -d verdeazul -X -q -t -A < db/pruebas/semilla.sql
-- Cada intento corre en una transacción que se deshace; los «deniega» tienen que terminar en ERROR.
\set ON_ERROR_STOP 0
SELECT max(id::text) FILTER (WHERE username = 'tec.ana') AS ana,
       max(id::text) FILTER (WHERE username = 'tec.tomas') AS tomas,
       max(id::text) FILTER (WHERE username = 'ver.bruno') AS bruno,
       max(id::text) FILTER (WHERE username = 'ver.carla') AS carla,
       max(id::text) FILTER (WHERE username = 'sup.sofia') AS sofia,
       max(id::text) FILTER (WHERE username = 'due.daniel') AS daniel,
       max(id::text) FILTER (WHERE username = 'due.rosa') AS rosa
FROM cuentas_usuario \gset
SELECT max(me.id::text) FILTER (WHERE f.codigo = 'F-001' AND pa.codigo = 'P-1' AND pe.nombre = '2026-II') AS m_t05,
       max(me.id::text) FILTER (WHERE f.codigo = 'F-003') AS m_t06,
       max(me.id::text) FILTER (WHERE f.codigo = 'F-004') AS m_t17
FROM negocio_medicion me JOIN negocio_parcela pa ON pa.id = me.parcela_id
JOIN negocio_finca f ON f.id = pa.finca_id JOIN negocio_periodo pe ON pe.id = me.periodo_id \gset

\echo == T-05: B aprueba la medicion que registro A (concede)
BEGIN;
UPDATE negocio_medicion SET estado = 'aprobada', aprobada_por_id = :'bruno', aprobada_en = now() WHERE id = :'m_t05';
ROLLBACK;
\echo == T-06: C, autora de la version 1 cuando era tecnica, intenta aprobarla (deniega)
BEGIN;
UPDATE negocio_medicion SET estado = 'aprobada', aprobada_por_id = :'carla', aprobada_en = now() WHERE id = :'m_t06';
ROLLBACK;
\echo == T-17: con 2026-I cerrado, B aprueba lo que A envio antes del cierre (concede)
BEGIN;
UPDATE negocio_medicion SET estado = 'aprobada', aprobada_por_id = :'bruno', aprobada_en = now() WHERE id = :'m_t17';
ROLLBACK;
\echo == T-04: A registra otra version en 2026-I, ya cerrado (deniega)
BEGIN;
INSERT INTO negocio_versionmedicion (id, medicion_id, numero, autor_id, fecha_medicion, fecha_registro, arboles,
    dap_promedio_cm, altura_promedio_m, toneladas_co2, observaciones, es_propuesta, huella_hoja_campo)
VALUES (gen_random_uuid(), :'m_t17', 2, :'ana', '2026-06-01', now(), 1, 1, 1, 1, '', false, '');
ROLLBACK;
\echo == T-38: S da a T, que tiene 20 asignaciones activas, la numero 21 (deniega)
BEGIN;
INSERT INTO negocio_asignacion (id, tecnico_id, finca_id, periodo_id, tipo, motivo, desde, creada_por_id, creada_en)
SELECT gen_random_uuid(), :'tomas', f.id, p.id, 'ordinaria', '', current_date, :'sofia', now()
FROM negocio_finca f, negocio_periodo p WHERE f.codigo = 'F-025' AND p.nombre = '2026-II';
ROLLBACK;

\echo == C1, C5 y T-27 por fila: que ve cada quien
SET ROLE va_app;
SELECT set_config('app.rol', 'TEC', false), set_config('app.usuario', :'ana', false) \gset
SELECT 'tec.ana ve (sin F-002, su temporal vencio): ' || string_agg(codigo, ',' ORDER BY codigo) FROM negocio_finca;
SELECT set_config('app.rol', 'DUE', false), set_config('app.usuario', :'rosa', false) \gset
SELECT 'due.rosa ve (fincas de T-002): ' || string_agg(codigo, ',' ORDER BY codigo) FROM negocio_finca;
SELECT set_config('app.usuario', :'daniel', false) \gset
SELECT 'due.daniel ve: ' || string_agg(codigo, ',' ORDER BY codigo) FROM negocio_finca;
SELECT 'due.daniel ve mediciones (solo aprobadas): ' || string_agg(estado, ',') FROM negocio_medicion;
SELECT set_config('app.rol', 'VER', false), set_config('app.usuario', :'bruno', false) \gset
SELECT 'ver.bruno ve fincas: ' || count(*) FROM negocio_finca;
RESET ROLE;
SELECT 'cadena de la bitacora rota en: ' || coalesce(bitacora_verificar()::text, 'ninguna');
