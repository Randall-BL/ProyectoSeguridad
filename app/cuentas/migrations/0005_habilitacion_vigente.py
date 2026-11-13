from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0005_habilitacion_vigente.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0004_intentos_y_cache"),
        ("negocio", "0003_seguridad_por_fila"),
    ]

    operations = [
        migrations.RunSQL(SQL, "DROP FUNCTION IF EXISTS va_habilitacion_vigente(uuid)"),
    ]
