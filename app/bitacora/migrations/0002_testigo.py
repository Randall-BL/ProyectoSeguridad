from pathlib import Path

from django.db import migrations, models

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0002_testigo.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("bitacora", "0001_initial"),
        ("nucleo", "0001_usuarios_de_base"),
    ]

    operations = [
        migrations.CreateModel(
            name="Testigo",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("instante", models.DateTimeField()),
                ("registro", models.BigIntegerField(help_text="Número del último registro de la bitácora sellado.")),
                ("huella", models.CharField(max_length=64)),
                ("tsa", models.URLField()),
                ("sello", models.TextField(help_text="Respuesta de la TSA (TimeStampResp, DER) en base64.")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.RunSQL(SQL, migrations.RunSQL.noop),
    ]
