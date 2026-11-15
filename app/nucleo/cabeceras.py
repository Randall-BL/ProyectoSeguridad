"""Cabeceras de seguridad que Django 5.2 no pone por su cuenta (tarea 9.4).

- Content-Security-Policy: la interfaz no usa JavaScript ni estilos en línea, así que no se permite
  ningún script; estilos e imágenes solo del propio origen. La única excepción es data: en las
  imágenes, por el código QR del autenticador (allauth lo entrega como data URI). Los formularios
  solo se envían al propio origen y nadie puede enmarcar la aplicación.
- Permissions-Policy: la aplicación no usa cámara, micrófono, ubicación ni pagos.
- Cross-Origin-Resource-Policy y Cross-Origin-Embedder-Policy: otros sitios no pueden incrustar sus
  respuestas, y la página solo carga recursos del propio origen.
- Cache-Control: las páginas no se guardan en cachés ni en el historial del navegador, porque
  muestran datos de las fincas y de las personas. Los estilos e imágenes conservan la caché larga
  que les pone WhiteNoise.

Va justo después de SecurityMiddleware, así también cubre lo que sirve WhiteNoise."""

POLITICA_DE_CONTENIDO = "; ".join([
    "default-src 'none'",
    "style-src 'self'",
    "img-src 'self' data:",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
])
PERMISOS = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


class CabecerasDeSeguridad:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        respuesta.headers.setdefault("Content-Security-Policy", POLITICA_DE_CONTENIDO)
        respuesta.headers.setdefault("Permissions-Policy", PERMISOS)
        respuesta.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        respuesta.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
        if respuesta.get("Content-Type", "").startswith("text/html"):
            respuesta.headers.setdefault("Cache-Control", "no-store")
        return respuesta
