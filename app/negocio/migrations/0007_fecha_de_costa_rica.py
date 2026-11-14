from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0007_fecha_de_costa_rica.sql").read_text(encoding="utf-8")

# Volver atrás deja las tres funciones como estaban: con current_date.
ANTERIOR = SQL.replace("va_hoy() BETWEEN", "current_date BETWEEN").replace(
    "desde <= va_hoy() AND (hasta IS NULL OR hasta >= va_hoy())",
    "desde <= current_date AND (hasta IS NULL OR hasta >= current_date)",
)


class Migration(migrations.Migration):

    dependencies = [
        ("negocio", "0006_certificados_y_trabajos"),
        ("autorizacion", "0002_hechos_flujos"),
    ]

    operations = [migrations.RunSQL(SQL, ANTERIOR)]
