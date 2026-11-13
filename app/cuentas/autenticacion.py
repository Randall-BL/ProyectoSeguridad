"""Quién puede autenticarse (tarea 3.9)."""

from allauth.account.auth_backends import AuthenticationBackend


class Autenticacion(AuthenticationBackend):
    """Además de estar activa, la cuenta tiene que tener un rol y estar dentro de su ventana. Django
    hace esta misma pregunta en cada petición al leer la sesión: cuando la ventana de AUD termina,
    la sesión abierta deja de valer en ese momento."""

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and user.puede_entrar()
