from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0002_permisos.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("negocio", "0001_initial"),
        ("cuentas", "0001_initial"),
        ("nucleo", "0001_usuarios_de_base"),
        ("sessions", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunSQL(SQL, migrations.RunSQL.noop)]
