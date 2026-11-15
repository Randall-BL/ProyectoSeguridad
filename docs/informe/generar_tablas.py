"""Tablas del informe a partir de la tabla de cobertura generada (docs/cobertura.csv y .md):
tabla-reglas.tex (resumen por regla) y tabla-cobertura.tex (Anexo A, permiso por permiso).

    python docs/informe/generar_tablas.py
"""

import csv
import re
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent


def tex(texto):
    texto = str(texto)
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                 ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")):
        texto = texto.replace(a, b)
    return texto


def corto(lugar):
    """politica/verdeazul/reglas.rego:17 -> reglas.rego:17; app/negocio/sql/0004_x.sql:6 -> 0004:6."""
    partes = []
    for pieza in lugar.split(";"):
        pieza = pieza.strip()
        if not pieza or pieza == "—":
            continue
        m = re.match(r".*/(\w+)/sql/(\d{4})_[^:]*\.sql:(\d+)$", pieza)
        partes.append(f"{m.group(1)} {m.group(2)}" if m else pieza.split("/")[-1])
    return ", ".join(dict.fromkeys(partes)) or "—"


def reglas():
    md = (RAIZ / "docs" / "cobertura.md").read_text(encoding="utf-8")
    bloque = md.split("## Reglas y casos de la Parte 1")[1].split("## Casos T")[0]
    filas = [f for f in bloque.splitlines() if f.startswith("| ") and not f.startswith("| Regla") and "---" not in f]
    lineas = [r"\begin{center}", r"\scriptsize", r"\renewcommand{\arraystretch}{1.0}",
              r"\begin{longtable}{@{}p{1.0cm} p{4.6cm} p{2.4cm} p{2.7cm} p{2.9cm} p{1.2cm}@{}}", r"\toprule",
              r"\cab{Regla} & \cab{Nombre} & \cab{Motor} & \cab{Base} & \cab{Casos T} & \cab{Pruebas} \\",
              r"\midrule", r"\endhead"]
    for f in filas:
        c = [x.strip() for x in f.strip("|").split("|")]
        regla, nombre, rego, base, casos, pruebas, _, resultado = c
        lineas.append(f"{tex(regla)} & {tex(nombre)} & {tex(corto(rego))} & {tex(corto(base))} & {tex(casos)} & "
                      f"{tex(pruebas)}{' ' if resultado == 'pasó' else ' (' + tex(resultado) + ')'} \\\\")
    lineas += [r"\bottomrule", r"\end{longtable}", r"\end{center}"]
    (AQUI / "tabla-reglas.tex").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def permisos():
    with (RAIZ / "docs" / "cobertura.csv").open(encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))
    lineas = [r"\begin{center}", r"\scriptsize", r"\renewcommand{\arraystretch}{1.05}", r"\setlength{\tabcolsep}{3pt}",
              r"\begin{longtable}{@{}p{0.6cm} p{1.7cm} p{1.2cm} p{0.9cm} p{3.4cm} p{2.6cm} p{3.4cm} p{0.8cm}@{}}",
              r"\toprule",
              r"\cab{Rol} & \cab{Objeto} & \cab{Verbo} & \cab{Reglas} & \cab{Dónde (ruta o componente)} & "
              r"\cab{Motor y base} & \cab{Prueba} & \cab{Resultado} \\",
              r"\midrule", r"\endhead"]
    for f in filas:
        prueba = f["prueba"]
        tipo = "pantalla" if prueba.startswith("test_cada_rol_entra") else ("objeto" if prueba.startswith(f"test_{f['rol'].lower()}_") else "")
        prueba_tex = f"({tipo})" if tipo == "pantalla" else tex(prueba).replace(r"\_", r"\_\allowbreak{}")
        motor_base = corto(f["rego"]) + ("; " + corto(f["base"]) if f["base"] != "—" else "")
        lineas.append(f"{tex(f['rol'])} & {tex(f['objeto']).replace(r'\_', r'\_\allowbreak{}')} & {tex(f['verbo'])} & "
                      f"{tex(f['condiciones'])} & {tex(f['ruta']).replace(', ', ', \\allowbreak{}')} & "
                      f"{tex(motor_base)} & {prueba_tex} & {tex(f['resultado'])} \\\\")
    lineas += [r"\bottomrule", r"\end{longtable}", r"\end{center}"]
    (AQUI / "tabla-cobertura.tex").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    reglas()
    permisos()
    print("tabla-reglas.tex y tabla-cobertura.tex listas")
