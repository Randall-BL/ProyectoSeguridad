-- Sesiones de servidor (tareas 3.5 y 3.6). va_app las crea, las corre en cada petición y las borra
-- al cerrar sesión o al revocarlas. Sin seguridad por fila: la sesión se busca por su
-- identificador antes de saber quién es la persona, y el identificador es lo que la protege.
GRANT SELECT, INSERT, UPDATE, DELETE ON cuentas_sesion TO va_app;
-- La tabla vieja de Django queda sin uso.
REVOKE ALL ON django_session FROM va_app;
