from pathlib import Path

from django.db import migrations

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0002_permisos_allauth.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0001_initial"),
        ("nucleo", "0001_usuarios_de_base"),
        ("account", "0009_emailaddress_unique_primary_email"),
        ("mfa", "0003_authenticator_type_uniq"),
    ]

    operations = [migrations.RunSQL(SQL, migrations.RunSQL.noop)]
