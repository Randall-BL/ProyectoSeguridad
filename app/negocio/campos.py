from django.db import models


class Poligono(models.Field):
    """Columna PostGIS geometry(Polygon, 4326) sin GeoDjango, que exigiría GDAL en la imagen.
    Se escribe en WKT («POLYGON((lon lat, …))») y se lee como EWKB en hexadecimal; las operaciones
    espaciales (área, traslape) las hace la base."""

    description = "Polígono en WGS 84"

    def db_type(self, connection):
        return "geometry(Polygon,4326)"

    def get_prep_value(self, value):
        if value in (None, ""):
            return None
        texto = str(value).strip()
        if texto.upper().startswith("SRID="):
            return texto
        return f"SRID=4326;{texto}"
