"""Intentos fallidos de inicio de sesión (POL-AU-07, tarea 3.7).

Desde el quinto fallo seguido, cada intento nuevo tiene que esperar: 30 segundos, luego 1, 2, 4
y 8 minutos. Al décimo, la cuenta queda bloqueada 15 minutos. Mientras dura la espera no se
comprueba la contraseña, ni siquiera la correcta. El conteo vive en la base, así que vale igual
en todas las instancias de Cloud Run, y se reinicia al entrar bien o tras un día sin fallos."""

import hashlib
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from cuentas.models import IntentosAcceso

DEMORA_DESDE = 5
BLOQUEO_EN = 10
DEMORA_INICIAL = timedelta(seconds=30)
BLOQUEO = timedelta(minutes=15)
OLVIDO = timedelta(days=1)


def _huella(nombre):
    return hashlib.sha256(nombre.strip().lower().encode()).hexdigest()


def espera_por(fallos):
    """Cuánto hay que esperar después de ese número de fallos seguidos."""
    if fallos >= BLOQUEO_EN:
        return BLOQUEO
    if fallos >= DEMORA_DESDE:
        return DEMORA_INICIAL * 2 ** (fallos - DEMORA_DESDE)
    return timedelta(0)


def espera_pendiente(nombre):
    """Hasta cuándo no se acepta otro intento con ese nombre, o None si ya se puede intentar."""
    fila = IntentosAcceso.objects.filter(pk=_huella(nombre)).first()
    if fila and fila.espera_hasta and fila.espera_hasta > timezone.now():
        return fila.espera_hasta
    return None


def registrar_fallo(nombre):
    """Suma un fallo y fija la espera que corresponde. Devuelve cuántos fallos seguidos van."""
    ahora = timezone.now()
    with transaction.atomic():
        fila, _ = IntentosAcceso.objects.select_for_update().get_or_create(pk=_huella(nombre))
        if fila.ultimo_fallo and ahora - fila.ultimo_fallo > OLVIDO:
            fila.fallos = 0
        fila.fallos += 1
        fila.ultimo_fallo = ahora
        espera = espera_por(fila.fallos)
        fila.espera_hasta = ahora + espera if espera else None
        fila.save()
    return fila.fallos


def olvidar(nombre):
    """Entró bien: los fallos anteriores dejan de contar."""
    IntentosAcceso.objects.filter(pk=_huella(nombre)).delete()


def mensaje_de_espera(hasta):
    segundos = max(1, int((hasta - timezone.now()).total_seconds()))
    if segundos < 90:
        cuanto = f"{segundos} segundos"
    else:
        cuanto = f"{-(-segundos // 60)} minutos"
    return f"Demasiados intentos fallidos. Espere {cuanto} antes de intentarlo de nuevo."
