"""Verifica cómo se habla con Google Sheets, usando un doble de gspread.

No se conecta a Google. Lo que se comprueba es que las llamadas que hace la app
sean las correctas: que las fórmulas se lean como fórmulas, que se guarde el
respaldo antes de tocar nada, y que el semáforo se pinte donde va.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sheets  # noqa: E402
from scraper.core import Producto  # noqa: E402
from sincronizar import CAMBIO, FALTANTE, NUEVO, construir_plan  # noqa: E402

fallos = []


def check(cond, etiqueta, extra=""):
    print(("  ok   " if cond else "  FALLA") + f"  {etiqueta}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        fallos.append(etiqueta)


# ─────────────────────────────────────────────── doble de gspread

class WorksheetFalsa:
    _siguiente_id = 100

    def __init__(self, title, valores=None):
        self.title = title
        self.id = WorksheetFalsa._siguiente_id
        WorksheetFalsa._siguiente_id += 1
        self._valores = valores or []
        self.row_count = max(len(self._valores), 10)
        self.col_count = 26
        self.bitacora = []

    def get_values(self, **kwargs):
        self.bitacora.append(("get_values", kwargs))
        return [list(f) for f in self._valores]

    def get_all_values(self):
        self.bitacora.append(("get_all_values", None))
        return [list(f) for f in self._valores]

    def clear(self):
        self.bitacora.append(("clear", None))
        self._valores = []

    def update(self, values=None, range_name=None, **kwargs):
        self.bitacora.append(("update", {"range_name": range_name, **kwargs}))
        self._valores = [list(f) for f in values]

    def append_rows(self, filas, **kwargs):
        self.bitacora.append(("append_rows", kwargs))
        self._valores += [list(f) for f in filas]

    def add_rows(self, n):
        self.row_count += n
        self.bitacora.append(("add_rows", n))

    def add_cols(self, n):
        self.col_count += n
        self.bitacora.append(("add_cols", n))

    def freeze(self, rows=0):
        self.bitacora.append(("freeze", rows))

    def format(self, rango, fmt):
        self.bitacora.append(("format", rango))


class WorksheetNotFound(Exception):
    pass


class SpreadsheetFalso:
    url = "https://docs.google.com/spreadsheets/d/FALSA"
    title = "Hoja de prueba"

    def __init__(self, hojas):
        self._hojas = {h.title: h for h in hojas}
        self.lotes = []

    def worksheet(self, title):
        if title not in self._hojas:
            raise WorksheetNotFound(title)
        return self._hojas[title]

    def add_worksheet(self, title, rows=100, cols=26):
        h = WorksheetFalsa(title)
        self._hojas[title] = h
        return h

    def worksheets(self):
        return list(self._hojas.values())

    def batch_update(self, cuerpo):
        self.lotes.append(cuerpo)
        return {}

    def del_worksheet(self, hoja):
        self._hojas.pop(hoja.title, None)

    def share(self, *a, **k):
        pass


class GspreadFalso:
    """Sustituye al módulo gspread, del que la app solo usa WorksheetNotFound."""
    WorksheetNotFound = WorksheetNotFound


sys.modules["gspread"] = GspreadFalso()


# ─────────────────────────────────────────────── datos de partida

ENCABEZADO = ["estado", "cambios", "revisado_en", "sku", "nombre", "precio", "foto", "notas"]
FILAS = [
    ["⚪ sin cambios", "", "2026-08-01 09:00", "S-1", "Silla", "100.00", '=IMAGE("https://cdn/s.jpg")', "ojo"],
    ["⚪ sin cambios", "", "2026-08-01 09:00", "Z-9", "Fantasma", "300.00", '=IMAGE("https://cdn/z.jpg")', ""],
]

hoja = WorksheetFalsa("Productos", [ENCABEZADO] + FILAS)
libro = SpreadsheetFalso([hoja])


class ClienteFalso:
    def open_by_key(self, key):
        return libro

    def open(self, nombre):
        return libro

    def create(self, titulo):
        return libro


sheets._cliente = lambda ruta=None: ClienteFalso()

# ─────────────────────────────────────────────── lectura
print("\n[1] Lectura de la hoja")
ctx = sheets.leer_hoja("https://docs.google.com/spreadsheets/d/ABC123", "Productos")
check(ctx["existe"] is True, "encuentra la pestaña")
check(ctx["encabezado"] == ENCABEZADO, "encabezado completo")
check(len(ctx["filas"]) == 2, "dos renglones", str(len(ctx["filas"])))

llamada = next(k for k in hoja.bitacora if k[0] == "get_values")
check(llamada[1].get("value_render_option") == "FORMULA",
      "se leen las FÓRMULAS, no su resultado (si no, se perderían las fotos)", str(llamada[1]))
check(ctx["filas"][0][6].startswith("=IMAGE("), "la fórmula llegó intacta", ctx["filas"][0][6])

print("\n[2] Pestaña que no existe")
ctx_vacio = sheets.leer_hoja("https://docs.google.com/spreadsheets/d/ABC123", "No existe")
check(ctx_vacio["existe"] is False and ctx_vacio["hoja"] is None, "se reporta como inexistente")
check(ctx_vacio["encabezado"] == [] and ctx_vacio["filas"] == [], "sin datos")

print("\n[3] Sin destino")
try:
    sheets.leer_hoja("", "Productos")
    check(False, "debe exigir la URL de la hoja")
except sheets.ErrorSheets as e:
    check("necesito la URL" in str(e), "mensaje claro", str(e))

# ─────────────────────────────────────────────── escritura
print("\n[4] Aplicar el plan")
productos = [
    Producto(nombre="Silla", sku="S-1", precio="120.00", imagen="https://cdn/s2.jpg"),
    Producto(nombre="Banco", sku="B-2", precio="75.00", imagen="https://cdn/b.jpg"),
]
plan = construir_plan(ctx["encabezado"], ctx["filas"], productos, ahora="2026-08-19 12:00")
check(plan.estados == [CAMBIO, FALTANTE, NUEVO], "plan esperado", str(plan.estados))

res = sheets.aplicar_plan(ctx, plan, respaldar=True, pestana="Productos")

respaldo = libro._hojas.get("Respaldo (antes de sincronizar)")
check(respaldo is not None, "se creó el respaldo")
if respaldo:
    check(respaldo._valores[0] == ENCABEZADO, "el respaldo guarda el encabezado anterior")
    check(len(respaldo._valores) == 3, "y los renglones anteriores", str(len(respaldo._valores)))
    check(respaldo._valores[1][6].startswith("=IMAGE("), "con sus fórmulas")

orden = [k[0] for k in hoja.bitacora]
check(orden.index("clear") < orden.index("update"), "primero limpia, luego escribe")
check("freeze" in orden, "congela el encabezado")

escrito = hoja._valores
check(escrito[0][:3] == ["estado", "cambios", "revisado_en"], "columnas de control al frente", str(escrito[0][:3]))
check("notas" in escrito[0], "la columna propia sigue ahí")
i_notas = escrito[0].index("notas")
check(escrito[1][i_notas] == "ojo", "y su valor no se perdió", escrito[1][i_notas])
i_foto = escrito[0].index("foto")
check(escrito[1][i_foto] == '=IMAGE("https://cdn/s2.jpg")', "la foto se refrescó", escrito[1][i_foto])
check(escrito[2][i_foto] == '=IMAGE("https://cdn/z.jpg")', "la del desaparecido se conservó", escrito[2][i_foto])

upd = next(k[1] for k in hoja.bitacora if k[0] == "update")
check(upd.get("value_input_option") == "USER_ENTERED",
      "se escribe como USER_ENTERED para que =IMAGE() funcione", str(upd))

print("\n[5] El semáforo")
peticiones = [p for lote in libro.lotes for p in lote.get("requests", [])]
colores = [p for p in peticiones if "repeatCell" in p]
check(len(colores) == 3, "un rango por renglón (ningún color se repite seguido)", str(len(colores)))
primero = colores[0]["repeatCell"]["range"]
check(primero["startRowIndex"] == 1, "el encabezado no se pinta", str(primero))
check(all(p["repeatCell"]["range"]["sheetId"] == hoja.id for p in colores), "todos apuntan a la pestaña correcta")
c1 = colores[0]["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"]
c2 = colores[1]["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"]
c3 = colores[2]["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"]
check(c1["blue"] < c1["red"], "renglón 1 amarillo (cambió)", str(c1))
check(c2["red"] > c2["green"], "renglón 2 rojo (no encontrado)", str(c2))
check(c3["green"] > c3["red"], "renglón 3 verde (nuevo)", str(c3))

dims = [p for p in peticiones if "updateDimensionProperties" in p]
check(len(dims) == 2, "se ajusta ancho de columna y alto de renglón para las fotos", str(len(dims)))

check(res["nuevos"] == 1 and res["cambiados"] == 1 and res["faltantes"] == 1, "resumen devuelto", str(res))
check(res["url"] == libro.url, "devuelve la liga de la hoja")

print("\n[6] Sincronizar sobre una pestaña que aún no existe")
hoja2 = WorksheetFalsa("Productos", [])
libro2 = SpreadsheetFalso([hoja2])
ctx2 = {"libro": libro2, "hoja": None, "encabezado": [], "filas": [], "existe": False}
plan2 = construir_plan([], [], productos, ahora="2026-08-19 12:00")
res2 = sheets.aplicar_plan(ctx2, plan2, respaldar=True, pestana="Nueva")
check("Nueva" in libro2._hojas, "crea la pestaña")
check("Respaldo (antes de sincronizar)" not in libro2._hojas, "no crea respaldo si no había nada")
check(res2["nuevos"] == 2, "las dos son altas", str(res2["nuevos"]))

print("\n[7] Escritura directa (modos reemplazar / nueva / agregar)")
from scraper import a_tabla  # noqa: E402

tabla_simple = a_tabla([
    Producto(nombre="Mesa", sku="M-1", precio="500.00", imagen="https://cdn/mesa.jpg"),
])

# 7.1 — "reemplazar" sobre una pestaña ya existente: se escribe con USER_ENTERED.
hoja3 = WorksheetFalsa("Productos", [["a"], ["b"]])
libro3 = SpreadsheetFalso([hoja3])
sheets._cliente = lambda ruta=None: type("C", (), {"open_by_key": lambda self, k: libro3})()
res3 = sheets.escribir(tabla_simple, destino="https://docs.google.com/spreadsheets/d/XYZ", modo="reemplazar")
upd3 = next(k[1] for k in hoja3.bitacora if k[0] == "update")
check(upd3.get("value_input_option") == "USER_ENTERED", "reemplazar usa USER_ENTERED", str(upd3))
check(hoja3.bitacora[0][0] == "clear", "reemplazar limpia antes de escribir")
check(res3["filas"] == 1, "reporta un renglón escrito")

# 7.2 — "agregar" sobre una pestaña que ya existe pero está vacía: antes se perdía la foto.
hoja4 = WorksheetFalsa("Productos", [])
libro4 = SpreadsheetFalso([hoja4])
sheets._cliente = lambda ruta=None: type("C", (), {"open_by_key": lambda self, k: libro4})()
sheets.escribir(tabla_simple, destino="https://docs.google.com/spreadsheets/d/XYZ", modo="agregar")
upd4 = next(k[1] for k in hoja4.bitacora if k[0] == "update")
check(upd4.get("value_input_option") == "USER_ENTERED",
      "agregar en pestaña vacía también usa USER_ENTERED (bug corregido)", str(upd4))
check(hoja4._valores[1][0].startswith("=IMAGE("), "la foto queda como fórmula, no como texto")

# 7.3 — "agregar" sobre una pestaña con datos: se anexa sin tocar lo anterior.
hoja5 = WorksheetFalsa("Productos", [["foto", "nombre"], ["=IMAGE(\"https://cdn/x.jpg\")", "Viejo"]])
libro5 = SpreadsheetFalso([hoja5])
sheets._cliente = lambda ruta=None: type("C", (), {"open_by_key": lambda self, k: libro5})()
sheets.escribir(tabla_simple, destino="https://docs.google.com/spreadsheets/d/XYZ", modo="agregar")
check("append_rows" in [k[0] for k in hoja5.bitacora], "usa append_rows en vez de reescribir")
check(hoja5._valores[1][1] == "Viejo", "el renglón anterior no se toca", hoja5._valores[1][1])
check(hoja5._valores[2][1] == "Mesa", "el nuevo se agrega al final", hoja5._valores[2][1])

# 7.4 — "nueva" agrega la fecha al nombre de la pestaña.
hoja6 = WorksheetFalsa("Sheet1", [])
libro6 = SpreadsheetFalso([hoja6])
sheets._cliente = lambda ruta=None: type("C", (), {"open_by_key": lambda self, k: libro6})()
res6 = sheets.escribir(tabla_simple, destino="https://docs.google.com/spreadsheets/d/XYZ",
                       pestana="Productos", modo="nueva")
check(res6["pestana"].startswith("Productos "), "el nombre lleva fecha y hora", res6["pestana"])

# 7.5 — al crear una hoja nueva desde cero, se borra el "Sheet1" que Google regala.
libro8 = SpreadsheetFalso([WorksheetFalsa("Sheet1", [])])
sheets._cliente = lambda ruta=None: type("C", (), {"create": lambda self, t: libro8})()
res8 = sheets.escribir(tabla_simple, destino="", pestana="Productos", modo="reemplazar")
check(res8["creado"] is True, "se marca como recién creada")
check("Sheet1" not in libro8._hojas, "se borra el 'Sheet1' que Google regala", list(libro8._hojas))
check("Productos" in libro8._hojas, "y queda la pestaña con nuestros datos")

print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron:")
    for f in fallos:
        print("  -", f)
    raise SystemExit(1)
print("Todas las pruebas pasaron.")
