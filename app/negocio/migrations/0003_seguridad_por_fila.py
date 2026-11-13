from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0003_seguridad_por_fila.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("negocio", "0002_permisos"),
        ("bitacora", "0001_initial"),
    ]

    operations = [migrations.RunSQL(SQL, migrations.RunSQL.noop)]
