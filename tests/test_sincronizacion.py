"""Pruebas de la sincronización contra una hoja existente.

Todo se prueba sin tocar Google: `construir_plan` solo recibe listas y devuelve
listas, así que se puede verificar exactamente qué se escribiría.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core import Producto  # noqa: E402
from sincronizar import (  # noqa: E402
    CAMBIO,
    COL_CAMBIOS,
    COL_ESTADO,
    COL_REVISION,
    FALTANTE,
    IGUAL,
    NUEVO,
    agrupar_colores,
    clave,
    construir_plan,
    peticiones_de_color,
)

fallos = []


def check(cond, etiqueta, extra=""):
    print(("  ok   " if cond else "  FALLA") + f"  {etiqueta}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        fallos.append(etiqueta)


def fila(plan, i) -> dict:
    return dict(zip(plan.encabezado, plan.filas[i]))


AHORA = "2026-08-19 12:00"


# ------------------------------------------------------------------ claves
print("\n[1] Emparejamiento")
check(clave({"sku": "abc-1"}) == "sku:ABC-1", "SKU en mayúsculas")
check(clave({"url_producto": "https://T.com/p/1/", "variante": "Azul"}) == "url:https://t.com/p/1|azul",
      "URL normalizada", clave({"url_producto": "https://T.com/p/1/", "variante": "Azul"}))
check(clave({"sku": "A", "url_producto": "https://x.com/1"}) == "sku:A", "el SKU tiene prioridad")
check(clave({"sku": "A", "url_producto": "https://x.com/1"}, "url") == "url:https://x.com/1|", "forzar URL")
check(clave({"sku": "", "url_producto": ""}) == "", "sin identificador")
check(clave({"url_producto": "https://x.com/1?utm=abc#top"}) == "url:https://x.com/1|",
      "se ignoran parámetros de rastreo", clave({"url_producto": "https://x.com/1?utm=abc#top"}))

# ------------------------------------------------------------------ hoja vacía
print("\n[2] Hoja vacía: todo es alta")
prods = [Producto(nombre="Silla", sku="S-1", precio="100.00"),
         Producto(nombre="Mesa", sku="M-1", precio="200.00")]
plan = construir_plan([], [], prods, ahora=AHORA)
check(plan.resumen["nuevos"] == 2, "dos altas", str(plan.resumen))
check(plan.estados == [NUEVO, NUEVO], "ambas en verde")
check(plan.encabezado[:3] == [COL_ESTADO, COL_CAMBIOS, COL_REVISION], "columnas de control al frente",
      str(plan.encabezado[:3]))
check(fila(plan, 0)[COL_REVISION] == AHORA, "sello de tiempo")

# ------------------------------------------------------------------ mezcla
print("\n[3] Altas, cambios, iguales y desaparecidos")
encabezado_previo = [COL_ESTADO, COL_CAMBIOS, COL_REVISION, "sku", "nombre", "precio", "inventario", "notas"]
filas_previas = [
    [IGUAL, "", "2026-08-01 09:00", "S-1", "Silla", "100.00", "5", "pedir más"],
    [IGUAL, "", "2026-08-01 09:00", "M-1", "Mesa", "200.00", "2", "favorita del cliente"],
    [IGUAL, "", "2026-08-01 09:00", "X-9", "Descontinuado", "50.00", "1", "revisar"],
]
prods = [
    Producto(nombre="Silla", sku="S-1", precio="100.00", inventario="5"),      # igual
    Producto(nombre="Mesa nueva", sku="M-1", precio="180.00", inventario="0"), # cambió
    Producto(nombre="Banco", sku="B-2", precio="75.00", inventario="9"),       # alta
]
plan = construir_plan(encabezado_previo, filas_previas, prods, ahora=AHORA)

check(plan.resumen == {**plan.resumen, "nuevos": 1, "cambiados": 1, "faltantes": 1, "iguales": 1},
      "un alta, un cambio, un desaparecido, un igual", str(plan.resumen))
check(plan.estados == [IGUAL, CAMBIO, FALTANTE, NUEVO], "orden y colores", str(plan.estados))

f0, f1, f2, f3 = (fila(plan, i) for i in range(4))
check(f1[COL_CAMBIOS] == "precio: 200.00 → 180.00; inventario: 2 → 0", "detalle del cambio", f1[COL_CAMBIOS])
check(f1["precio"] == "180.00" and f1["nombre"] == "Mesa nueva", "datos actualizados", f1["precio"])
check(f1["notas"] == "favorita del cliente", "columna propia intacta en el cambio", f1["notas"])
check(f2["precio"] == "50.00" and f2["nombre"] == "Descontinuado", "el desaparecido no se toca", f2["precio"])
check(f2["notas"] == "revisar", "columna propia intacta en el desaparecido", f2["notas"])
check(f2[COL_REVISION] == "2026-08-01 09:00", "el desaparecido conserva su última revisión", f2[COL_REVISION])
check(f0[COL_REVISION] == AHORA and f1[COL_REVISION] == AHORA, "los encontrados se resellan")
check(f0[COL_CAMBIOS] == "", "sin cambios no se anota nada", f0[COL_CAMBIOS])
check(f3["sku"] == "B-2" and f3[COL_ESTADO] == NUEVO, "el alta va al final", f3["sku"])
check(f3["notas"] == "", "el alta deja vacías tus columnas", repr(f3["notas"]))
check("notas" in plan.encabezado, "tu columna sigue existiendo")
check(plan.resumen["columnas_propias"] == ["notas"], "se reporta la columna propia",
      str(plan.resumen["columnas_propias"]))

# ------------------------------------------------------------------ formatos
print("\n[4] Tolerancia al formato de los números")
plan = construir_plan(
    ["sku", "precio", "inventario"],
    [["S-1", "1299", "10"]],
    [Producto(nombre="X", sku="S-1", precio="1299.00", inventario="10")],
    ahora=AHORA,
)
check(plan.estados == [IGUAL], "1299 y 1299.00 son el mismo precio", str(plan.estados))

plan = construir_plan(
    ["sku", "precio"],
    [["S-1", "1299.00"]],
    [Producto(nombre="X", sku="S-1", precio="1299.50")],
    ahora=AHORA,
)
check(plan.estados == [CAMBIO], "50 centavos sí son un cambio", str(plan.estados))

# ------------------------------------------------------------------ fórmulas
print("\n[5] Las fórmulas de foto sobreviven")
plan = construir_plan(
    ["sku", "foto", "precio"],
    [["S-1", '=IMAGE("https://cdn/a.jpg")', "100.00"],
     ["Z-9", '=IMAGE("https://cdn/z.jpg")', "300.00"]],
    [Producto(nombre="X", sku="S-1", precio="100.00", imagen="https://cdn/b.jpg")],
    ahora=AHORA,
)
check(fila(plan, 0)["foto"] == '=IMAGE("https://cdn/b.jpg")', "la foto encontrada se refresca",
      fila(plan, 0)["foto"])
check(fila(plan, 1)["foto"] == '=IMAGE("https://cdn/z.jpg")', "la foto del desaparecido se conserva",
      fila(plan, 1)["foto"])

# ------------------------------------------------------------------ sin clave
print("\n[6] Renglones sin identificador")
plan = construir_plan(
    ["sku", "nombre", "url_producto"],
    [["", "Escrito a mano", ""]],
    [Producto(nombre="Otro", sku="A-1")],
    ahora=AHORA,
)
check(plan.estados == [FALTANTE, NUEVO], "el renglón sin clave queda en rojo", str(plan.estados))
check("no tienen SKU ni liga" in plan.aviso, "se avisa el motivo", plan.aviso)
check(fila(plan, 0)["nombre"] == "Escrito a mano", "y su contenido no se pierde")

print("\n[7] Identificadores repetidos")
plan = construir_plan(
    ["sku", "precio"],
    [["S-1", "100.00"], ["S-1", "999.00"]],
    [Producto(nombre="X", sku="S-1", precio="150.00")],
    ahora=AHORA,
)
check(plan.estados == [CAMBIO, FALTANTE], "solo el primero se empareja", str(plan.estados))
check("comparten identificador" in plan.aviso, "se avisa la repetición", plan.aviso)

print("\n[8] Emparejamiento por URL cuando no hay SKU")
plan = construir_plan(
    ["url_producto", "variante", "precio"],
    [["https://t.com/p/1", "Azul", "100.00"]],
    [Producto(nombre="X", url_producto="https://t.com/p/1/", variante="Azul", precio="120.00")],
    ahora=AHORA,
)
check(plan.estados == [CAMBIO], "empareja por liga aunque cambie la diagonal final", str(plan.estados))

plan = construir_plan(
    ["url_producto", "variante", "precio"],
    [["https://t.com/p/1", "Azul", "100.00"]],
    [Producto(nombre="X", url_producto="https://t.com/p/1", variante="Rojo", precio="120.00")],
    ahora=AHORA,
)
check(plan.estados == [FALTANTE, NUEVO], "otra variante es otro producto", str(plan.estados))

# ------------------------------------------------------------------ colores
print("\n[9] Semáforo")
check(agrupar_colores([NUEVO, NUEVO, CAMBIO, NUEVO]) == [(0, 2, NUEVO), (2, 3, CAMBIO), (3, 4, NUEVO)],
      "renglones seguidos se agrupan", str(agrupar_colores([NUEVO, NUEVO, CAMBIO, NUEVO])))
check(agrupar_colores([]) == [], "lista vacía")
peticiones = peticiones_de_color(123, [NUEVO, CAMBIO])
r0 = peticiones[0]["repeatCell"]["range"]
check(r0["startRowIndex"] == 1 and r0["endRowIndex"] == 2, "se salta el encabezado", str(r0))
check(peticiones[0]["repeatCell"]["range"]["sheetId"] == 123, "id de la pestaña")
verde = peticiones[0]["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"]
check(verde["green"] > verde["red"], "el verde es verde", str(verde))
amarillo = peticiones[1]["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"]
check(amarillo["blue"] < amarillo["red"], "el amarillo es amarillo", str(amarillo))

print("\n[10] Corridas repetidas son estables")
enc, fls = None, None
prods = [Producto(nombre="Silla", sku="S-1", precio="100.00")]
plan1 = construir_plan([], [], prods, ahora=AHORA)
plan2 = construir_plan(plan1.encabezado, plan1.filas, prods, ahora=AHORA)
check(plan2.estados == [IGUAL], "la segunda corrida no inventa cambios", str(plan2.estados))
check(plan2.encabezado == plan1.encabezado, "el encabezado no crece en cada corrida")
plan3 = construir_plan(plan2.encabezado, plan2.filas, prods, ahora=AHORA)
check(plan3.encabezado == plan1.encabezado and plan3.estados == [IGUAL], "y sigue estable a la tercera")

print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron:")
    for f in fallos:
        print("  -", f)
    raise SystemExit(1)
print("Todas las pruebas pasaron.")
