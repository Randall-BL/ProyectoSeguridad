"""Días hábiles (lunes a viernes) en la hora de Costa Rica: el plazo de diez días para corregir una
enmienda (C9), los dos días que tiene SUP para una alerta (C15) y el registro tardío de una
medición (más de cinco días entre la medición y el registro piden motivo). La base tiene la misma
cuenta en va_dias_habiles()."""

from datetime import date, datetime, timedelta

from django.utils import timezone


def _fecha(valor):
    if valor is None:
        return timezone.localdate()
    if isinstance(valor, datetime):
        return timezone.localtime(valor).date() if timezone.is_aware(valor) else valor.date()
    return valor


def dias_habiles(desde, hasta=None):
    """Días hábiles después de «desde» y hasta «hasta» (hoy si no se da), inclusive."""
    inicio, fin = _fecha(desde), _fecha(hasta)
    cuenta, dia = 0, inicio + timedelta(days=1)
    while dia <= fin:
        if dia.isoweekday() < 6:
            cuenta += 1
        dia += timedelta(days=1)
    return cuenta


__all__ = ["dias_habiles", "date"]
