-- Corrección de la seguridad por fila (encontrada al construir la pantalla de 5.6): al insertar una
-- medición, la política de TEC preguntaba va_tec_medicion(id), que busca la fila nueva en la tabla
-- antes de que exista, así que ningún técnico podía registrar una medición. Al insertar se revisa
-- la parcela (C1: asignación vigente a su finca) y que quien la crea sea quien pide.
DROP POLICY va_app_inserta ON negocio_medicion;
CREATE POLICY va_app_inserta ON negocio_medicion FOR INSERT TO va_app WITH CHECK (
    va_escribe()
    AND (va_rol() <> 'TEC' OR (va_tec_parcela(parcela_id) AND creada_por_id = va_usuario()))
);
