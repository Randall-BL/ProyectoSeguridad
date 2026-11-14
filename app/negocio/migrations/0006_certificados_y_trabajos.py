from pathlib import Path

from django.db import migrations, models

SQL = (Path(__file__).resolve().parent.parent / "sql" / "0006_certificados_y_trabajos.sql").read_text(encoding="utf-8")

ANTERIOR = """
REVOKE EXECUTE ON FUNCTION va_dias_habiles(date, date) FROM va_trabajos;
REVOKE UPDATE (escalada_en) ON negocio_alerta FROM va_trabajos;
REVOKE SELECT (usuario_id, expire_date), DELETE ON cuentas_sesion FROM va_trabajos;
REVOKE SELECT (date_joined, username, supervisor_id) ON cuentas_usuario FROM va_trabajos;
DROP FUNCTION va_comprobar(text);
DROP TRIGGER regla_certificado ON negocio_certificado;
DROP FUNCTION va_certificado_c4();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("negocio", "0005_tec_inserta_medicion"),
        ("cuentas", "0005_habilitacion_vigente"),
        ("autorizacion", "0002_hechos_flujos"),
    ]

    operations = [
        migrations.AddField(
            model_name="alerta",
            name="escalada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunSQL(SQL, ANTERIOR),
    ]
