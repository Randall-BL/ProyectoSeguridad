from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0002_hechos_flujos.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("autorizacion", "0001_hechos"),
    ]

    operations = [
        migrations.RunSQL(
            SQL,
            "DROP FUNCTION IF EXISTS va_hechos_certificado(uuid), va_hechos_titular(uuid, uuid), "
            "va_hechos_enmienda(uuid), va_hechos_asignacion(uuid, uuid), va_es_tecnico(uuid), "
            "va_asignaciones_activas(uuid), va_dias_habiles(date, date)",
        ),
    ]
