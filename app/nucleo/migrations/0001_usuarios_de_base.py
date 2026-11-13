from django.db import migrations

# Un usuario de base por componente (tarea 2.3). Ninguno es dueño de las tablas: el dueño es el
# usuario con el que se migra. Nacen sin poder iniciar sesión; el LOGIN y la clave se los pone
# infra/crear-secretos.sh cuando su componente existe (va_app ya los tiene en Neon).
ROLES = ("va_app", "va_emision", "va_publico", "va_trabajos")

CREAR = "\n".join(
    f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{rol}') "
    f"THEN CREATE ROLE {rol} NOLOGIN; END IF; END $$;"
    for rol in ROLES
) + (
    "\nDO $$ BEGIN EXECUTE format('GRANT CONNECT ON DATABASE %I TO "
    + ", ".join(ROLES)
    + "', current_database()); END $$;"
)


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.RunSQL(CREAR, migrations.RunSQL.noop)]
