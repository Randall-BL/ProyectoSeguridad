from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0004_reglas_en_la_base.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [("negocio", "0003_seguridad_por_fila")]

    operations = [migrations.RunSQL(SQL, migrations.RunSQL.noop)]
