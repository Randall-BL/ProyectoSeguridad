from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0001_hechos.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("negocio", "0004_reglas_en_la_base"),
        ("cuentas", "0005_habilitacion_vigente"),
    ]

    operations = [
        migrations.RunSQL(
            SQL,
            "DROP FUNCTION IF EXISTS va_hechos_finca(uuid), va_hechos_nueva_medicion(uuid, uuid, uuid), "
            "va_hechos_medicion(uuid, uuid), va_hechos_sujeto(uuid, text, uuid), va_hoy()",
        ),
    ]
