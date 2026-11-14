# Demostración de certificados (tarea 6.9, caso T-32)

Archivos reales del despliegue v0.4.0. El certificado `VA-2026-I-QXWJWM9G` lo emitió el servicio de
emisión el 13 de noviembre de 2026, cuando el trabajo diario pidió lo pendiente: la medición de F-001
P-1 del período 2026-I, aprobada en la semilla.

| Archivo | Qué es | Resultado esperado |
|---|---|---|
| `certificado-valido.json` | El certificado tal como lo descarga quien puede leerlo | Válido |
| `certificado-alterado.json` | El mismo, con las toneladas cambiadas de 55.895 a 56.895 | No válido: la firma ya no corresponde |

## 1. Sin conexión (lo que haría un comprador)

```
pip install cryptography
python verificador/verificar.py docs/demostracion/certificado-valido.json     # sale con 0
python verificador/verificar.py docs/demostracion/certificado-alterado.json   # sale con 1
```

## 2. En el servicio público

https://verdeazul-publico-708901712393.us-east1.run.app

- «Con el archivo»: subir cada uno de los dos archivos.
- «Con el código»: `VA-2026-I-QXWJWM9G` responde sello válido, vigente, 55.895 toneladas, período 2026-I.

## 3. Un certificado revocado consultado por código (en vivo)

Se hace en la presentación, con cuatro personas distintas (C7 a C10):

1. G (`ger.gabriela`, GER) solicita una enmienda de esa medición, con A como responsable.
2. A (`tec.ana`, TEC) corrige las toneladas: la enmienda queda material.
3. C (`ver.carla`, VER) da el dictamen favorable. B, que aprobó la medición, no puede (C10, T-23).
4. G intenta autorizarla y se le niega (C8, T-24). La otra gerente (`ger.gerardo`) la autoriza (T-12).
5. Al confirmar, la aplicación pide la reemisión: el servicio revoca `VA-2026-I-QXWJWM9G` y emite el
   reemplazo en la misma transacción (T-25).
6. En el servicio público, el código viejo responde «Certificado revocado» y enlaza al nuevo (T-32).

Las pruebas automáticas `flujos.tests_casos` y `flujos.tests_certificados` recorren el mismo camino.
