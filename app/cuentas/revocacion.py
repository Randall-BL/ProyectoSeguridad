"""Revocación inmediata (POL-CA-04, POL-CA-05, tarea 3.6).

Cuando cambia lo que una persona puede hacer, se borran todas sus sesiones abiertas, en la misma
transacción que el cambio: la siguiente petición desde cualquier equipo ya no tiene sesión y le
pide entrar de nuevo, con el rol y el alcance nuevos. Pasa al cambiar el rol, la vigencia o la
contraseña de la cuenta, al darla de baja, al aprobar una propuesta de rol o una habilitación y al
crear o terminar una asignación.

Las actualizaciones masivas (QuerySet.update) no disparan estas señales: el trabajo de
vencimientos (7.2) cierra las sesiones él mismo."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from bitacora.registro import anexar
from cuentas.models import EstadoPropuesta, PropuestaRol, Sesion, Usuario
from negocio.models import Asignacion

# Campos de la cuenta que cambian lo que la persona puede hacer.
CAMPOS_QUE_REVOCAN = ("rol", "is_active", "password", "vigente_desde", "vigente_hasta")


def cerrar_sesiones(usuario_id, regla):
    """Borra todas las sesiones de la persona y lo deja en la bitácora."""
    borradas, _ = Sesion.objects.filter(usuario_id=usuario_id).delete()
    if borradas:
        anexar(
            accion="cerrar_sesiones",
            resultado="concedido",
            objeto_tipo="cuenta",
            objeto_id=usuario_id,
            regla=regla,
        )
    return borradas


@receiver(pre_save, sender=Usuario)
def _comparar_cuenta(sender, instance, raw=False, update_fields=None, **kwargs):
    instance._revocar_por = ""
    if raw or instance._state.adding:
        return
    if update_fields is not None and not set(update_fields) & set(CAMPOS_QUE_REVOCAN):
        return
    anterior = Usuario.objects.filter(pk=instance.pk).values(*CAMPOS_QUE_REVOCAN).first()
    if anterior is None:
        return
    if anterior["is_active"] and not instance.is_active:
        instance._revocar_por = "POL-CA-05"
    elif any(anterior[campo] != getattr(instance, campo) for campo in CAMPOS_QUE_REVOCAN):
        instance._revocar_por = "POL-CA-04"


@receiver(post_save, sender=Usuario)
def _revocar_por_cuenta(sender, instance, raw=False, **kwargs):
    if not raw and getattr(instance, "_revocar_por", ""):
        cerrar_sesiones(instance.pk, instance._revocar_por)


@receiver(post_save, sender=PropuestaRol)
def _revocar_por_rol(sender, instance, raw=False, **kwargs):
    if not raw and instance.estado == EstadoPropuesta.APROBADA:
        cerrar_sesiones(instance.usuario_id, "POL-CA-04")


@receiver(post_save, sender=Asignacion)
def _revocar_por_asignacion(sender, instance, raw=False, **kwargs):
    if not raw:
        cerrar_sesiones(instance.tecnico_id, "POL-CA-04")
