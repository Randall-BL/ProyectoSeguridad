from pathlib import Path

from django.db import migrations

CARPETA = Path(__file__).resolve().parent.parent / "sql"
SQL = (CARPETA / "0003_h3_confirmada.sql").read_text(encoding="utf-8")
ANTERIOR = (CARPETA / "0003_anterior.sql").read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("autorizacion", "0002_hechos_flujos"),
        ("negocio", "0006_certificados_y_trabajos"),
    ]

    operations = [migrations.RunSQL(SQL, ANTERIOR)]
