-- Escenario de prueba de la seguridad por fila y de las reglas en la base (tareas 2.5 y 2.6).
-- Correr SOLO contra una base desechable (la de docker compose), con un usuario dueño:
--   psql "postgresql://postgres@127.0.0.1:55432/verdeazul" -X -q -t -A -f db/pruebas/reglas.sql
-- Cada bloque «debe fallar» tiene que terminar en ERROR; los demás muestran lo que ve cada rol.
\set ON_ERROR_STOP 0
-- datos de prueba (como dueño)
INSERT INTO cuentas_usuario (id, password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, rol, identificacion)
SELECT gen_random_uuid(), '!', false, u, initcap(u), '', '', false, true, now(), r, u FROM (VALUES
 ('tec_a','TEC'),('tec_x','TEC'),('ver_b','VER'),('ver_c','VER'),('sup_s','SUP'),('ger_g','GER'),('adm','ADM'),('aud_e','AUD'),('due_d','DUE')) v(u,r);
CREATE TABLE prueba_u AS SELECT username, id FROM cuentas_usuario;
GRANT SELECT ON prueba_u TO va_app;
INSERT INTO negocio_titular (id, codigo, tipo, creado_en) VALUES (gen_random_uuid(),'T1','fisica',now()),(gen_random_uuid(),'T2','sociedad',now());
INSERT INTO negocio_datospersonales (id, titular_id, nombre, identificacion, telefono, correo, direccion) SELECT gen_random_uuid(), id, 'Titular '||codigo, '1-0000-'||codigo, '', '', '' FROM negocio_titular;
INSERT INTO negocio_finca (id, codigo, nombre, titular_id, ubicacion, estado, creada_en) SELECT gen_random_uuid(), 'F'||substr(codigo,2), 'Finca '||codigo, id, 'PZ', 'aprobado', now() FROM negocio_titular;
INSERT INTO negocio_parcela (id, finca_id, codigo, geometria, version, activa, estado) SELECT gen_random_uuid(), f.id, 'P1', 'SRID=4326;POLYGON((-83.70 9.37,-83.69 9.37,-83.69 9.38,-83.70 9.38,-83.70 9.37))', 1, true, 'aprobado' FROM negocio_finca f WHERE codigo='F1';
INSERT INTO negocio_parcela (id, finca_id, codigo, geometria, version, activa, estado) SELECT gen_random_uuid(), f.id, 'P2', 'SRID=4326;POLYGON((-83.68 9.37,-83.67 9.37,-83.67 9.38,-83.68 9.38,-83.68 9.37))', 1, true, 'aprobado' FROM negocio_finca f WHERE codigo='F2';
INSERT INTO negocio_periodo (id, nombre, inicio, fin_medicion, cierre_registro, estado) VALUES (gen_random_uuid(),'2026-II','2026-07-01','2026-12-15','2026-12-20','abierto'),(gen_random_uuid(),'2026-I','2026-01-01','2026-06-15','2026-06-20','cerrado');
INSERT INTO negocio_asignacion (id, tecnico_id, finca_id, periodo_id, tipo, motivo, desde, creada_por_id, creada_en)
 SELECT gen_random_uuid(), (SELECT id FROM prueba_u WHERE username='tec_a'), (SELECT id FROM negocio_finca WHERE codigo='F1'), (SELECT id FROM negocio_periodo WHERE nombre='2026-II'), 'ordinaria', '', '2026-07-01', (SELECT id FROM prueba_u WHERE username='sup_s'), now();
INSERT INTO negocio_representacion (id, usuario_id, titular_id, desde, documento) SELECT gen_random_uuid(), (SELECT id FROM prueba_u WHERE username='due_d'), id, '2026-01-01', '' FROM negocio_titular WHERE codigo='T1';
INSERT INTO negocio_medicion (id, parcela_id, periodo_id, estado, creada_por_id, creada_en, observaciones)
 SELECT gen_random_uuid(), (SELECT id FROM negocio_parcela WHERE codigo='P1'), (SELECT id FROM negocio_periodo WHERE nombre='2026-II'), 'borrador', (SELECT id FROM prueba_u WHERE username='tec_a'), now(), '';
INSERT INTO negocio_versionmedicion (id, medicion_id, numero, autor_id, fecha_medicion, fecha_registro, arboles, dap_promedio_cm, altura_promedio_m, toneladas_co2, observaciones, es_propuesta, huella_hoja_campo)
 SELECT gen_random_uuid(), (SELECT id FROM negocio_medicion), 1, (SELECT id FROM prueba_u WHERE username='tec_a'), '2026-10-01', now(), 120, 25.5, 14.2, 38.4, '', false, '';

\echo == C11: parcela que se traslapa con P1 (debe fallar)
INSERT INTO negocio_parcela (id, finca_id, codigo, geometria, version, activa, estado) SELECT gen_random_uuid(), f.id, 'P3', 'SRID=4326;POLYGON((-83.695 9.375,-83.685 9.375,-83.685 9.385,-83.695 9.385,-83.695 9.375))', 1, true, 'aprobado' FROM negocio_finca f WHERE codigo='F2';
SELECT 'area de P1 calculada por la base: ' || area_ha || ' ha' FROM negocio_parcela WHERE codigo='P1';

\echo == C19: asignar a un verificador sin habilitacion y asignarse a si mismo (deben fallar)
INSERT INTO negocio_asignacion (id, tecnico_id, finca_id, periodo_id, tipo, motivo, desde, creada_por_id, creada_en) SELECT gen_random_uuid(), (SELECT id FROM prueba_u WHERE username='ver_b'), (SELECT id FROM negocio_finca WHERE codigo='F2'), (SELECT id FROM negocio_periodo WHERE nombre='2026-II'), 'ordinaria', '', '2026-07-01', (SELECT id FROM prueba_u WHERE username='sup_s'), now();
INSERT INTO negocio_asignacion (id, tecnico_id, finca_id, periodo_id, tipo, motivo, desde, creada_por_id, creada_en) SELECT gen_random_uuid(), (SELECT id FROM prueba_u WHERE username='tec_a'), (SELECT id FROM negocio_finca WHERE codigo='F2'), (SELECT id FROM negocio_periodo WHERE nombre='2026-II'), 'ordinaria', '', '2026-07-01', (SELECT id FROM prueba_u WHERE username='tec_a'), now();

\echo == K-1: con el maximo en 1, una segunda asignacion activa para tec_a (debe fallar)
UPDATE negocio_parametrorol SET max_asignaciones_activas = 1 WHERE rol = 'TEC';
INSERT INTO negocio_asignacion (id, tecnico_id, finca_id, periodo_id, tipo, motivo, desde, hasta, creada_por_id, creada_en) SELECT gen_random_uuid(), (SELECT id FROM prueba_u WHERE username='tec_a'), (SELECT id FROM negocio_finca WHERE codigo='F2'), (SELECT id FROM negocio_periodo WHERE nombre='2026-II'), 'temporal', 'apoyo', '2026-11-06', '2026-11-09', (SELECT id FROM prueba_u WHERE username='sup_s'), now();
UPDATE negocio_parametrorol SET max_asignaciones_activas = 20 WHERE rol = 'TEC';

\echo == C2: version con fecha fuera del periodo y medicion en periodo cerrado (deben fallar)
INSERT INTO negocio_versionmedicion (id, medicion_id, numero, autor_id, fecha_medicion, fecha_registro, arboles, dap_promedio_cm, altura_promedio_m, toneladas_co2, observaciones, es_propuesta, huella_hoja_campo) SELECT gen_random_uuid(), (SELECT id FROM negocio_medicion), 2, (SELECT id FROM prueba_u WHERE username='tec_a'), '2026-05-01', now(), 1, 1, 1, 1, '', false, '';
INSERT INTO negocio_medicion (id, parcela_id, periodo_id, estado, creada_por_id, creada_en, observaciones) SELECT gen_random_uuid(), (SELECT id FROM negocio_parcela WHERE codigo='P1'), (SELECT id FROM negocio_periodo WHERE nombre='2026-I'), 'borrador', (SELECT id FROM prueba_u WHERE username='tec_a'), now(), '';

\echo == C1 y C5 por fila: que ve cada quien
SET ROLE va_app;
SELECT set_config('app.rol','TEC',false), set_config('app.usuario',(SELECT id::text FROM prueba_u WHERE username='tec_a'),false) \gset
SELECT 'tec_a (asignado a F1) ve fincas: ' || coalesce(string_agg(codigo, ','), 'nada') FROM negocio_finca;
SELECT 'tec_a ve datos personales de: ' || coalesce(string_agg(nombre, ','), 'nadie') FROM negocio_datospersonales;
SELECT set_config('app.usuario',(SELECT id::text FROM prueba_u WHERE username='tec_x'),false) \gset
SELECT 'tec_x (sin asignacion) ve fincas: ' || coalesce(string_agg(codigo, ','), 'nada') FROM negocio_finca;
SELECT set_config('app.rol','DUE',false), set_config('app.usuario',(SELECT id::text FROM prueba_u WHERE username='due_d'),false) \gset
SELECT 'due_d (titular T1) ve fincas: ' || coalesce(string_agg(codigo, ','), 'nada') FROM negocio_finca;
SELECT 'due_d ve mediciones en borrador: ' || count(*) FROM negocio_medicion;
SELECT set_config('app.rol','VER',false), set_config('app.usuario',(SELECT id::text FROM prueba_u WHERE username='ver_b'),false) \gset
SELECT 'ver_b ve fincas: ' || coalesce(string_agg(codigo, ','), 'nada') FROM negocio_finca;
SELECT set_config('app.rol','',false) \gset
SELECT 'sin rol ve fincas: ' || coalesce(string_agg(codigo, ','), 'nada') FROM negocio_finca;
\echo == AUD no escribe
SELECT set_config('app.rol','AUD',false), set_config('app.usuario',(SELECT id::text FROM prueba_u WHERE username='aud_e'),false) \gset
WITH c AS (UPDATE negocio_finca SET nombre = 'x' RETURNING 1) SELECT 'filas que AUD cambio: ' || count(*) FROM c;
WITH c AS (INSERT INTO negocio_titular (id, codigo, tipo, creado_en) VALUES (gen_random_uuid(),'T9','fisica',now()) RETURNING 1) SELECT 'titulares que AUD inserto: ' || count(*) FROM c;
INSERT INTO negocio_finca (id, codigo, nombre, titular_id, ubicacion, estado, creada_en) SELECT gen_random_uuid(), 'F9', 'x', id, '', 'propuesto', now() FROM negocio_titular WHERE codigo='T1';
RESET ROLE;

\echo == C3 y K-2: quien registro no aprueba (por id de usuario)
UPDATE negocio_medicion SET estado = 'enviada';
UPDATE negocio_medicion SET estado = 'aprobada', aprobada_por_id = (SELECT id FROM prueba_u WHERE username='tec_a'), aprobada_en = now();
UPDATE negocio_medicion SET estado = 'aprobada', aprobada_por_id = (SELECT id FROM prueba_u WHERE username='ver_b'), aprobada_en = now();
SELECT 'estado tras la aprobacion de ver_b: ' || estado FROM negocio_medicion;
\echo == C5: ya aprobada, el duenno la ve
SET ROLE va_app;
SELECT set_config('app.rol','DUE',false), set_config('app.usuario',(SELECT id::text FROM prueba_u WHERE username='due_d'),false) \gset
SELECT 'due_d ve mediciones aprobadas: ' || count(*) FROM negocio_medicion;
RESET ROLE;
\echo == C16: suprimir datos de un titular con certificado reciente (debe fallar)
INSERT INTO negocio_certificado (id, codigo, medicion_id, parcela_id, periodo_id, toneladas_co2, estado, emitido_en, contenido, firma, clave_id) SELECT gen_random_uuid(), 'VA-PRUEBA-1', m.id, m.parcela_id, m.periodo_id, 38.4, 'vigente', now(), '{}', '', '' FROM negocio_medicion m;
UPDATE negocio_datospersonales SET suprimido_en = now() WHERE titular_id = (SELECT id FROM negocio_titular WHERE codigo='T1');
\echo == C4: segundo certificado vigente para la misma parcela y periodo (debe fallar)
INSERT INTO negocio_certificado (id, codigo, medicion_id, parcela_id, periodo_id, toneladas_co2, estado, emitido_en, contenido, firma, clave_id) SELECT gen_random_uuid(), 'VA-PRUEBA-2', m.id, m.parcela_id, m.periodo_id, 38.4, 'vigente', now(), '{}', '', '' FROM negocio_medicion m;
\echo == C12: proponerse un rol a si mismo (debe fallar)
INSERT INTO cuentas_propuestarol (id, usuario_id, rol, es_habilitacion, propuesta_por_id, propuesta_en, estado) SELECT gen_random_uuid(), id, 'GER', false, id, now(), 'propuesta' FROM prueba_u WHERE username='adm';
