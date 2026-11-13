from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0005_tec_inserta_medicion.sql").read_text(encoding="utf-8")

ANTERIOR = """
DROP POLICY va_app_inserta ON negocio_medicion;
CREATE POLICY va_app_inserta ON negocio_medicion FOR INSERT TO va_app
    WITH CHECK (va_escribe() AND (va_rol() <> 'TEC' OR (va_tec_medicion(id))));
"""


class Migration(migrations.Migration):

    dependencies = [("negocio", "0004_reglas_en_la_base")]

    operations = [migrations.RunSQL(SQL, ANTERIOR)]
