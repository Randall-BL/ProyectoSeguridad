"""Tabla de cobertura de la matriz para el informe (tarea 8.7, sale a docs/cobertura.md).

Para cada uno de los 102 permisos de politica/matriz.json dice dónde está (la regla en Rego, la
ruta que lo ejerce y el candado de la base) y qué prueba lo comprueba; para cada regla C1–C20 y
H1–H4, sus casos T de la Parte 1 y las pruebas que los ejecutan; y las 38 celdas denegadas. Con
los registros de una corrida de las pruebas marca cada una como pasada o no.

    python manage.py test --verbosity 2 > django.log 2>&1          (en app/)
    opa test -v politica > opa.log
    python -m unittest -v > emision.log 2>&1                        (en emision/, publico/, ...)
    python infra/cobertura.py --resultados django.log opa.log emision.log ...

Sin --resultados la tabla sale igual, con la columna de resultado en «sin correr».
"""

import argparse
import ast
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Las reglas de la Parte 1 (Entregable 3) y los casos T que las prueban.
REGLAS = {
    "C1": ("Asignación vigente", ["T-01", "T-02", "T-27"]),
    "C2": ("Edición solo en borrador", ["T-01", "T-03", "T-04", "T-21", "T-30"]),
    "C3": ("Quien registró no aprueba (K-2)", ["T-05", "T-06", "T-17", "T-26", "T-40"]),
    "C4": ("Emisión única", ["T-07", "T-25"]),
    "C5": ("Solo lo suyo", ["T-08"]),
    "C6": ("Ventana de auditoría", ["T-09"]),
    "C7": ("Solicitar enmienda", ["T-11", "T-21"]),
    "C8": ("Autorización final", ["T-12", "T-24"]),
    "C9": ("Corregir dentro del plazo", ["T-13"]),
    "C10": ("Revisión técnica independiente", ["T-14", "T-23"]),
    "C11": ("Catálogo con segunda firma", ["T-15"]),
    "C12": ("Nadie se administra a sí mismo", ["T-16"]),
    "C13": ("Credenciales y declaración propias", ["T-35"]),
    "C14": ("Apertura y cierre entre dos", ["T-04", "T-17", "T-22"]),
    "C15": ("Alertas ajenas", ["T-36"]),
    "C16": ("Supresión condicionada", ["T-37"]),
    "C17": ("Abstención por vínculo", ["T-29"]),
    "C18": ("Exportar evidencia", ["T-31"]),
    "C19": ("Asignar con vigencia y máximo de activas (K-1)", ["T-27", "T-28", "T-38", "T-39"]),
    "C20": ("Comprobación pública", ["T-32"]),
    "H1": ("Frecuencia", ["T-02", "T-18"]),
    "H2": ("Tiempo", ["T-34"]),
    "H3": ("Combinada", ["T-19", "T-33"]),
    "H4": ("Secuencia (C3, C8, C10)", ["T-06", "T-14", "T-24"]),
    "K-3": ("Motor caído: fallo cerrado", ["T-41"]),
    "Filas": ("Filas sin acceso (AUD no escribe, OPE no entra)", ["T-10", "T-20"]),
}

# Dónde decide el motor cada control de historial y la falla cerrada (las C están en reglas.rego).
REGO_EXTRA = {"H1": "h1_nivel", "H2": '"H2"', "H3": "h3_activa", "H4": 'cumple contains "C3"', "K-3": "default decision",
              "C17": "abstencion if"}

# Permisos de SIS y PUB: no tienen pantalla; los ejerce otro componente.
OTROS_COMPONENTES = {
    "leer": "emision/emitir.py (lee lo necesario para emitir con va_emision)",
    "emitir": "emision/emitir.py: emitir() (6.3)",
    "revocar": "emision/emitir.py: reemitir() (6.5)",
    "anexar": "bitacora_anexar() en cada acción",
    "crear": "autorizacion/historial.py: alertar() (alertas de H1 a H3)",
    "comprobar": "publico/servicio.py: /comprobar (6.7)",
}
PRUEBA_OTROS = {
    "leer": ["flujos.tests_certificados.EmisionDeCertificados.test_emite_una_medicion_aprobada_con_contenido_firmado"],
    "emitir": ["flujos.tests_certificados.EmisionDeCertificados.test_emite_una_medicion_aprobada_con_contenido_firmado"],
    "revocar": ["flujos.tests_certificados.EmisionDeCertificados.test_t25_una_enmienda_que_cambia_toneladas_revoca_y_reemite"],
    "anexar": ["bitacora.tests.CadenaDeLaBitacora.test_la_cadena_de_la_semilla_esta_integra"],
    "crear": ["flujos.tests_casos.CasosQueFaltaban.test_t18_h1_mas_fincas_que_el_umbral_pide_segundo_factor_y_motivo"],
    "comprobar": ["test_servicio.ComprobacionPublica.test_un_codigo_vigente"],
}


def _linea(archivo, patron):
    """Primera línea de un archivo que contiene el patrón, como archivo:línea."""
    for numero, texto in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1):
        if patron in texto:
            return f"{archivo.relative_to(RAIZ).as_posix()}:{numero}"
    return ""


def en_rego(regla):
    reglas = RAIZ / "politica" / "verdeazul" / "reglas.rego"
    decision = RAIZ / "politica" / "verdeazul" / "decision.rego"
    if regla in REGO_EXTRA:
        return _linea(decision, REGO_EXTRA[regla]) or _linea(reglas, REGO_EXTRA[regla])
    if regla.startswith("C"):
        return _linea(reglas, f'cumple contains "{regla}"')
    return ""


def en_la_base(regla):
    """El segundo candado: los SQL de disparadores, restricciones y seguridad por fila que nombran la
    regla. Los de autorizacion/sql son los hechos que se le pasan al motor, no un candado."""
    lugares = []
    patron = re.compile(rf"\b{re.escape(regla)}\b")
    archivos = [a for carpeta in ("negocio", "cuentas", "bitacora") for a in (RAIZ / "app" / carpeta / "sql").glob("*.sql")]
    for archivo in sorted(archivos):
        for numero, texto in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1):
            if patron.search(texto):
                lugares.append(f"{archivo.relative_to(RAIZ).as_posix()}:{numero}")
                break
    return lugares


def rutas():
    """(verbo, objeto) -> nombres de ruta, leyendo @protegida en las vistas y los path() de urls.py."""
    funciones = {}
    for archivo in (RAIZ / "app" / "flujos" / "vistas").glob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        for m in re.finditer(r'@protegida\("(\w+)", "(\w+)"[^\n]*\n(?:@[^\n]*\n)*def (\w+)', texto):
            funciones[(archivo.stem, m.group(3))] = (m.group(1), m.group(2))
    por_permiso = defaultdict(list)
    urls = (RAIZ / "app" / "flujos" / "urls.py").read_text(encoding="utf-8")
    for m in re.finditer(r'path\("([^"]*)", (\w+)\.(\w+), name="(\w+)"\)', urls):
        clave = funciones.get((m.group(2), m.group(3)))
        if clave:
            por_permiso[clave].append(m.group(4))
    exportar = (RAIZ / "app" / "flujos" / "vistas" / "exportar.py").read_text(encoding="utf-8")
    for tipo in re.findall(r'^    "(\w+)": _\w+,$', exportar, re.MULTILINE):
        por_permiso[("exportar", tipo)].append(f"exportar_{tipo}")
    return por_permiso


def pruebas():
    """Las pruebas del repositorio: id -> nombre, y caso T -> ids que lo ejecutan."""
    por_caso = defaultdict(list)
    ids = []
    archivos = list((RAIZ / "app").glob("*/tests*.py")) + [p for p in RAIZ.glob("*/test_*.py")]
    for archivo in archivos:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        if archivo.is_relative_to(RAIZ / "app"):
            modulo = ".".join(archivo.relative_to(RAIZ / "app").with_suffix("").parts)
        else:
            modulo = archivo.stem
        for clase in [n for n in arbol.body if isinstance(n, ast.ClassDef)]:
            for funcion in [n for n in clase.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]:
                identificador = f"{modulo}.{clase.name}.{funcion.name}"
                ids.append(identificador)
                for numero in re.findall(r"(?:^|_)t(\d\d)(?=_)", funcion.name):
                    por_caso[f"T-{numero}"].append(identificador)
    rego = (RAIZ / "politica" / "verdeazul" / "decision_test.rego").read_text(encoding="utf-8")
    for nombre in re.findall(r"^(test_\w+) if", rego, re.MULTILINE):
        identificador = f"rego.{nombre}"
        ids.append(identificador)
        for numero in re.findall(r"(?:^|_)t(\d\d)(?=_)", nombre):
            por_caso[f"T-{numero}"].append(identificador)
    return ids, por_caso


def resultados(archivos):
    """Lee la salida de manage.py test -v 2, de unittest -v y de opa test -v."""
    estado = {}
    for archivo in archivos or []:
        lineas = Path(archivo).read_text(encoding="utf-8", errors="replace").splitlines()
        pendiente = None
        for texto in lineas:
            # Puede venir pegado a otra salida en la misma línea (las migraciones no terminan en salto).
            m = re.search(r"\b(test_\w+) \(([\w.]+?)(?:\.test_\w+)?\)", texto)
            if m:
                clase = m.group(2)
                pendiente = f"{clase}.{m.group(1)}" if not clase.endswith(m.group(1)) else clase
            if pendiente:
                fin = re.search(r"\.\.\. (ok|FAIL|ERROR|skipped)", texto) or re.match(r"^(ok|FAIL|ERROR)$", texto.strip())
                if fin:
                    estado[pendiente] = {"ok": "pasó", "FAIL": "falló", "ERROR": "falló"}.get(fin.group(1), "omitida")
                    pendiente = None
            m = re.match(r"^data\.verdeazul(?:_test)?\.(test_\w+): (PASS|FAIL|ERROR)", texto)
            if m:
                estado[f"rego.{m.group(1)}"] = "pasó" if m.group(2) == "PASS" else "falló"
    return estado


def _resultado(ids, estado):
    if not estado:
        return "sin correr"
    vistos = [estado.get(i) for i in ids]
    if any(v == "falló" for v in vistos):
        return "falló"
    if any(v == "pasó" for v in vistos) and all(v in ("pasó", "omitida") for v in vistos):
        return "pasó"
    if any(v == "pasó" for v in vistos):
        return "pasó (parcial)"
    return "sin dato"


def main():
    lector = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lector.add_argument("--resultados", nargs="*", help="Salidas de las pruebas (Django -v 2, unittest -v, opa test -v).")
    lector.add_argument("--salida", default=str(RAIZ / "docs" / "cobertura.md"))
    opciones = lector.parse_args()

    matriz = json.loads((RAIZ / "politica" / "matriz.json").read_text(encoding="utf-8"))["matriz"]
    por_permiso = rutas()
    todas, por_caso = pruebas()
    estado = resultados(opciones.resultados)

    filas = []
    for rol, celdas in matriz["celdas"].items():
        for objeto, lista in celdas.items():
            for permiso in lista:
                verbo, condiciones = permiso["verbo"], permiso.get("condiciones", [])
                reglas = [c for c in condiciones if c != matriz["lectura_vigilada"]]
                if rol in matriz["roles_de_la_aplicacion"]:
                    nombres = por_permiso.get((verbo, objeto), [])
                    if any(_sin_objeto(n) for n in nombres):
                        ids = ["flujos.tests_casos.CasoFelizPorPermiso.test_cada_rol_entra_a_lo_que_la_matriz_le_concede"]
                    else:
                        ids = [f"flujos.tests_casos.CasoFelizSobreObjetos.test_{rol.lower()}_{verbo}_{objeto}"]
                    donde = ", ".join(nombres) or "—"
                else:
                    ids = PRUEBA_OTROS.get(verbo, [])
                    donde = OTROS_COMPONENTES.get(verbo, "—")
                casos = sorted({t for r in reglas for t in REGLAS.get(r, ("", []))[1]})
                filas.append({
                    "rol": rol, "objeto": objeto, "verbo": verbo,
                    "condiciones": ", ".join(condiciones) or "—",
                    "rego": "; ".join(filter(None, (en_rego(r) for r in reglas))) or "matriz.json",
                    "ruta": donde,
                    "base": "; ".join(sorted({lugar for r in reglas for lugar in en_la_base(r)})) or "—",
                    "prueba": ", ".join(i.split(".")[-1] for i in ids),
                    "casos": ", ".join(casos) or "—",
                    "resultado": _resultado(ids + [i for t in casos for i in por_caso.get(t, [])], estado),
                })

    denegadas = [(rol, objeto) for rol, celdas in matriz["celdas"].items() for objeto, lista in celdas.items() if not lista]
    prueba_denegadas = ["rego.test_lo_que_no_esta_en_la_matriz_se_deniega", "rego.test_la_matriz_tiene_102_permisos_y_38_celdas_denegadas",
                        "flujos.tests_idor.IdentificadorAjeno.test_con_cada_rol_un_identificador_ajeno_no_da_nada"]

    reglas_filas = []
    for codigo, (nombre, casos) in REGLAS.items():
        ids = [i for t in casos for i in por_caso.get(t, [])]
        sin_prueba = [t for t in casos if not por_caso.get(t)]
        reglas_filas.append({
            "regla": codigo, "nombre": nombre, "rego": en_rego(codigo) or "—",
            "base": "; ".join(en_la_base(codigo)) or "—", "casos": ", ".join(casos),
            "pruebas": len(ids), "sin_prueba": ", ".join(sin_prueba) or "ninguno",
            "resultado": _resultado(ids, estado),
        })

    casos_todos = sorted({t for _, casos in REGLAS.values() for t in casos} | {"T-38", "T-39", "T-40"}, key=lambda t: int(t[2:]))
    casos_filas = [{"caso": t, "pruebas": por_caso.get(t, []), "resultado": _resultado(por_caso.get(t, []), estado)}
                   for t in casos_todos]

    _escribir(opciones.salida, matriz, filas, denegadas, prueba_denegadas, reglas_filas, casos_filas, estado, todas)


def _sin_objeto(nombre_ruta):
    """Las rutas sin identificador en su patrón (listas, altas, exportaciones)."""
    urls = (RAIZ / "app" / "flujos" / "urls.py").read_text(encoding="utf-8")
    m = re.search(rf'path\("([^"]*)", [\w.]+, name="{re.escape(nombre_ruta)}"\)', urls)
    return nombre_ruta.startswith("exportar_") or bool(m and "<" not in m.group(1))


def _escribir(salida, matriz, filas, denegadas, prueba_denegadas, reglas_filas, casos_filas, estado, todas):
    total = len(filas)
    aplicacion = sum(1 for f in filas if f["rol"] in matriz["roles_de_la_aplicacion"])
    pasaron = sum(1 for f in filas if f["resultado"].startswith("pasó"))
    corridas = sum(1 for i in todas if i in estado)
    lineas = [
        "# Cobertura de la matriz",
        "",
        "Generado por `infra/cobertura.py` a partir de `politica/matriz.json`, del código y de los registros de",
        "las pruebas. No se edita a mano: se vuelve a generar.",
        "",
        f"- Permisos concedidos: **{total}** ({aplicacion} de los siete roles de la aplicación, "
        f"{total - aplicacion} de SIS y PUB). Con su prueba en verde: **{pasaron}**.",
        f"- Celdas denegadas: **{len(denegadas)}**.",
        f"- Pruebas encontradas en el repositorio: {len(todas)}; con resultado en esta corrida: {corridas}.",
        "",
        "## Reglas y casos de la Parte 1",
        "",
        "| Regla | Nombre | Motor (Rego) | Base | Casos T | Pruebas | Casos sin prueba | Resultado |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in reglas_filas:
        lineas.append(f"| {r['regla']} | {r['nombre']} | {r['rego']} | {r['base']} | {r['casos']} | {r['pruebas']} | "
                      f"{r['sin_prueba']} | {r['resultado']} |")
    lineas += ["", "## Casos T y sus pruebas", "", "| Caso | Pruebas | Resultado |", "|---|---|---|"]
    for c in casos_filas:
        nombres = "<br>".join(f"`{p}`" for p in c["pruebas"]) or "—"
        lineas.append(f"| {c['caso']} | {nombres} | {c['resultado']} |")
    lineas += ["", "## Los permisos concedidos", "",
               "| Rol | Objeto | Verbo | Condiciones | Motor (Rego) | Ruta o componente | Base | Prueba del caso feliz | Casos de sus reglas | Resultado |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for f in filas:
        lineas.append(f"| {f['rol']} | {f['objeto']} | {f['verbo']} | {f['condiciones']} | {f['rego']} | {f['ruta']} | "
                      f"{f['base']} | `{f['prueba']}` | {f['casos']} | {f['resultado']} |")
    lineas += ["", "## Celdas denegadas", "",
               "Todas se deniegan por la matriz en el motor, antes de mirar el objeto; las prueban "
               + ", ".join(f"`{p.split('.')[-1]}` ({_resultado([p], estado)})" for p in prueba_denegadas) + ".", ""]
    por_rol = defaultdict(list)
    for rol, objeto in denegadas:
        por_rol[rol].append(objeto)
    lineas += ["| Rol | Objetos sin ningún permiso |", "|---|---|"]
    for rol, objetos in por_rol.items():
        lineas.append(f"| {rol} | {', '.join(objetos)} |")
    Path(salida).write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    with Path(salida).with_suffix(".csv").open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"{salida}: {total} permisos, {pasaron} con su prueba en verde; {len(denegadas)} celdas denegadas.")


if __name__ == "__main__":
    main()
