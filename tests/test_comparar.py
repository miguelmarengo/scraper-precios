"""Pruebas del emparejamiento entre tiendas distintas (modo «comparar»).

Todo se prueba sin tocar Google: `construir_comparacion` solo recibe listas
y devuelve un plan; `.tabla()` solo recibe un dict de confirmaciones.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comparar import (  # noqa: E402
    columnas_tienda,
    construir_comparacion,
    tienda_de_columna,
)
from scraper.core import Producto  # noqa: E402

fallos = []


def check(cond, etiqueta, extra=""):
    print(("  ok   " if cond else "  FALLA") + f"  {etiqueta}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        fallos.append(etiqueta)


def fila(tabla, i) -> dict:
    return dict(zip(tabla[0], tabla[i + 1]))


# ------------------------------------------------------------------ columnas
print("\n[1] Nombres de columna por tienda")
check(columnas_tienda("Liverpool") == (
    "precio · Liverpool", "disponible · Liverpool", "liga · Liverpool", "actualizado · Liverpool",
), "cuatro columnas por tienda", str(columnas_tienda("Liverpool")))
check(tienda_de_columna("precio · Liverpool") == "Liverpool", "se extrae el nombre de la tienda")
check(tienda_de_columna("liga · Liverpool") == "Liverpool", "también la columna de la liga")
check(tienda_de_columna("nombre") is None, "una columna normal no es de ninguna tienda")

# ------------------------------------------------------------------ tablero nuevo
print("\n[2] Primer tablero: todo es nuevo")
prods = [
    Producto(nombre="Sillón Oslo", variante="Blanco", precio="12999.00", disponible="Sí",
              url_producto="https://palaciodehierro.com/sillon-oslo"),
    Producto(nombre="Mesa Roble", variante="", precio="5000.00", disponible="Sí",
              url_producto="https://palaciodehierro.com/mesa-roble"),
]
plan = construir_comparacion([], [], prods, "Palacio de Hierro")
check(plan.resumen["exactos"] == 0 and plan.resumen["extraidos"] == 2, "nada que emparejar todavía",
      str(plan.resumen))
tabla, resumen = plan.tabla()
check(resumen["nuevos_finales"] == 2, "las dos filas son nuevas", str(resumen))
check("precio · Palacio de Hierro" in tabla[0], "columna de la tienda creada", str(tabla[0]))
check("liga · Palacio de Hierro" in tabla[0], "columna de la liga directa creada", str(tabla[0]))
check("🏆 mejor precio" in tabla[0], "columna de mejor precio creada", str(tabla[0]))
check("decisión" in tabla[0], "columna de decisión (viendo/favorito/comprado) creada", str(tabla[0]))
check(fila(tabla, 0)["producto"] == "Sillón Oslo", "el nombre quedó como producto canónico")
check(fila(tabla, 0)["liga · Palacio de Hierro"] == "https://palaciodehierro.com/sillon-oslo",
      "se guarda la liga directa al producto", fila(tabla, 0)["liga · Palacio de Hierro"])
check(fila(tabla, 0)["🏆 mejor precio"] == "$12,999.00 · Palacio de Hierro",
      "con una sola tienda, ella misma es la mejor", fila(tabla, 0)["🏆 mejor precio"])

# ------------------------------------------------------------------ segunda tienda: coincidencia exacta
print("\n[3] Segunda tienda: nombre idéntico se empareja solo")
prods2 = [
    # mismo producto, más barato en Liverpool
    Producto(nombre="Sillón Oslo", variante="Blanco", precio="11999.00", disponible="Sí",
              url_producto="https://liverpool.com.mx/sillon-oslo"),
    Producto(nombre="Lámpara de piso", variante="", precio="899.00", disponible="Sí"),        # nuevo
]
plan2 = construir_comparacion(tabla[0], tabla[1:], prods2, "Liverpool")
check(plan2.resumen["exactos"] == 1, "el sillón coincidió solo", str(plan2.resumen))
tabla2, resumen2 = plan2.tabla()
check(resumen2["nuevos_finales"] == 1, "solo la lámpara es nueva", str(resumen2))
check(resumen2["total_final"] == 3, "el tablero crece a 3 productos", str(resumen2))
f_sillon = next(f for f in [fila(tabla2, i) for i in range(len(tabla2) - 1)] if f["producto"] == "Sillón Oslo")
check(f_sillon["precio · Palacio de Hierro"] == "12999.00", "conserva el precio de la primera tienda",
      f_sillon["precio · Palacio de Hierro"])
check(f_sillon["precio · Liverpool"] == "11999.00", "y agrega el de la segunda", f_sillon["precio · Liverpool"])
check(f_sillon["liga · Liverpool"] == "https://liverpool.com.mx/sillon-oslo",
      "también guarda la liga de la segunda tienda", f_sillon["liga · Liverpool"])
check(f_sillon["🏆 mejor precio"] == "$11,999.00 · Liverpool",
      "el mejor precio se recalcula entre las dos tiendas", f_sillon["🏆 mejor precio"])
check("precio · Palacio de Hierro" in tabla2[0] and "precio · Liverpool" in tabla2[0],
      "las dos columnas de tienda conviven", str(tabla2[0]))

# ------------------------------------------------------------------ coincidencia dudosa
print("\n[4] Nombre parecido pero no idéntico: pide confirmación")
plan3 = construir_comparacion(tabla2[0], tabla2[1:], [
    Producto(nombre="Sillon Oslo Blanco", variante="", precio="10999.00", disponible="Sí"),
], "West Elm")
check(len(plan3.candidatos) == 1, "se detecta como candidato, no como exacto", str(plan3.resumen))
check(plan3.resumen["exactos"] == 0, "no se empareja solo", str(plan3.resumen))

tabla3_sin_confirmar, resumen3_sin = plan3.tabla()
check(resumen3_sin["nuevos_finales"] == 1, "sin confirmar, se agrega como renglón nuevo", str(resumen3_sin))

indice = plan3.candidatos[0].indice_producto
tabla3_confirmado, resumen3_si = plan3.tabla({indice: True})
check(resumen3_si["nuevos_finales"] == 0, "confirmado, no se agrega como nuevo", str(resumen3_si))
check(resumen3_si["total_final"] == 3, "se fusiona con el renglón existente", str(resumen3_si))
f = next(f for f in [fila(tabla3_confirmado, i) for i in range(len(tabla3_confirmado) - 1)]
         if f["producto"] == "Sillón Oslo")
check(f["precio · West Elm"] == "10999.00", "el precio de la tercera tienda queda en el mismo renglón",
      f["precio · West Elm"])

# ------------------------------------------------------------------ producto totalmente distinto
print("\n[5] Producto sin nada parecido: renglón nuevo, sin candidatos")
plan4 = construir_comparacion(tabla2[0], tabla2[1:], [
    Producto(nombre="Refrigerador", variante="Acero", precio="15000.00"),
], "Home Depot")
check(not plan4.candidatos, "no hay nada suficientemente parecido", str(plan4.resumen))
tabla4, resumen4 = plan4.tabla()
check(resumen4["nuevos_finales"] == 1, "se agrega como nuevo")

# ------------------------------------------------------------------ duplicados en la misma corrida
print("\n[6] Duplicados dentro de la misma corrida")
plan5 = construir_comparacion([], [], [
    Producto(nombre="Foco 20W", precio="50.00"),
    Producto(nombre="Foco 20W", precio="55.00"),
], "Walmart")
check(plan5.resumen["duplicados"] == 1, "el segundo se cuenta como duplicado, no se agrega dos veces",
      str(plan5.resumen))
tabla5, resumen5 = plan5.tabla()
check(resumen5["total_final"] == 1, "solo un renglón final", str(resumen5))

print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron:")
    for f in fallos:
        print("  -", f)
    raise SystemExit(1)
print("Todas las pruebas pasaron.")
