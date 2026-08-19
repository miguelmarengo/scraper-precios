"""Pruebas contra un servidor local que imita una tienda Shopify y una genérica."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fixture_server import arrancar  # noqa: E402

from scraper import scrapear  # noqa: E402
from scraper.core import normalizar_precio  # noqa: E402
from scraper.shipping import extraer_tiempo_entrega  # noqa: E402

fallos = []


def check(cond, etiqueta, extra=""):
    print(("  ok   " if cond else "  FALLA") + f"  {etiqueta}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        fallos.append(etiqueta)


# ---------------------------------------------------------------- unitarias
print("\n[1] Normalización de precios")
casos = [("$1,234.50", "1234.50"), ("1.234,50 €", "1234.50"), ("MXN 249", "249.00"),
         (319.5, "319.50"), ("1,50", "1.50"), ("1,500", "1500.00"), ("", ""), (None, ""), ("agotado", "")]
for entrada, esperado in casos:
    got = normalizar_precio(entrada)
    check(got == esperado, f"normalizar_precio({entrada!r}) == {esperado!r}", f"dio {got!r}")

print("\n[2] Detección de tiempo de entrega")
entregas = [
    ("<div>Entrega estimada de 3 a 5 días hábiles</div>", "3 a 5 días hábiles"),
    ("<p>Recíbelo en 2 días hábiles</p>", "2 días hábiles"),
    ("<span>Envío el mismo día</span>", "Envío el mismo día"),
    ("<div>Ships in 5 business days</div>", "5 días hábiles"),
    ("<div>Nada relevante aquí</div>", ""),
]
for html, esperado in entregas:
    got = extraer_tiempo_entrega(html)
    check(got == esperado, f"entrega {html[:38]}… -> {esperado!r}", f"dio {got!r}")

# ---------------------------------------------------------------- Shopify
print("\n[3] Tienda Shopify simulada")
srv_s, url_s = arrancar(modo="shopify")
prods, informe = scrapear(url_s, max_productos=50, delay=0.0, workers=2)
check(informe["plataforma"] == "Shopify", "detecta Shopify", informe["plataforma"])
check(len(prods) == 5, "5 filas (todas las variantes)", str(len(prods)))
por_sku = {p.sku: p for p in prods}
check(set(por_sku) == {"TZ-AZ-CH", "TZ-RJ-GR", "PL-22", "SO-BL", "SO-NE"}, "SKUs correctos", str(set(por_sku)))
a = por_sku.get("TZ-AZ-CH")
if a:
    check(a.precio == "249.00", "precio variante", a.precio)
    check(a.precio_lista == "299.00", "precio de lista", a.precio_lista)
    check(a.moneda == "MXN", "moneda desde el tema", a.moneda)
    check(a.disponible == "Sí", "disponibilidad", a.disponible)
    check(a.inventario == "42", "inventario desde products/<handle>.js", a.inventario)
    check(a.tiempo_entrega == "3 a 5 días hábiles", "tiempo de entrega", a.tiempo_entrega)
    check("Color: Azul" in a.caracteristicas and "Tamaño: Chico" in a.caracteristicas, "características de opciones", a.caracteristicas)
    check("microondas" in a.descripcion, "descripción limpia de HTML", a.descripcion[:60])
    check(a.marca == "Alfarería Sur", "marca", a.marca)
b = por_sku.get("TZ-RJ-GR")
if b:
    check(b.disponible == "No" and b.inventario == "0", "agotado -> inventario 0", f"{b.disponible}/{b.inventario}")
c = por_sku.get("PL-22")
if c:
    check(c.variante == "", "variante 'Default Title' se omite", repr(c.variante))
srv_s.shutdown()

# ---------------------------------------------------------------- Genérico
print("\n[4] Tienda genérica con JSON-LD")
srv_g, url_g = arrancar(modo="generico")
prods, informe = scrapear(url_g, max_productos=50, delay=0.0, workers=2)
check(len(prods) == 2, "2 productos del sitemap (páginas institucionales filtradas)", str(len(prods)))
por_nombre = {p.nombre: p for p in prods}
s = por_nombre.get("Silla nórdica")
check(s is not None, "encuentra 'Silla nórdica'", str(list(por_nombre)))
if s:
    check(s.precio == "1899.00", "precio de JSON-LD", s.precio)
    check(s.moneda == "MXN", "moneda de JSON-LD", s.moneda)
    check(s.sku == "SN-001", "sku", s.sku)
    check(s.marca == "Muebles Test", "marca anidada", s.marca)
    check(s.disponible == "Sí", "InStock -> Sí", s.disponible)
    check(s.inventario == "12", "inventario por texto 'solo quedan N'", s.inventario)
    check(s.tiempo_entrega == "5 días hábiles", "entrega", s.tiempo_entrega)
    check("Garantía: 2 años" in s.caracteristicas, "additionalProperty", s.caracteristicas)
    check("Material: Roble" in s.caracteristicas, "material", s.caracteristicas)
m = por_nombre.get("Mesa de roble")
if m:
    check(m.disponible == "No" and m.inventario == "0", "OutOfStock -> No / 0", f"{m.disponible}/{m.inventario}")
srv_g.shutdown()

# ---------------------------------------------------------------- WooCommerce
print("\n[5] Tienda WooCommerce simulada")
srv_w, url_w = arrancar(modo="woo")
prods, informe = scrapear(url_w, max_productos=50, delay=0.0, workers=2)
check(informe["plataforma"] == "WooCommerce", "detecta WooCommerce", informe["plataforma"])
check(len(prods) == 2, "2 productos", str(len(prods)))
por_sku = {p.sku: p for p in prods}
cafe = por_sku.get("CAF-1K")
if cafe:
    check(cafe.precio == "389.00", "precio escalado por currency_minor_unit", cafe.precio)
    check(cafe.precio_lista == "450.00", "precio regular escalado", cafe.precio_lista)
    check(cafe.moneda == "MXN", "moneda", cafe.moneda)
    check(cafe.disponible == "Si".replace("i", "\u00ed"), "en stock", cafe.disponible)
    check(cafe.inventario == "4", "low_stock_remaining", cafe.inventario)
    check(cafe.categoria == "Caf\u00e9, Despensa", "categorias unidas", cafe.categoria)
    check("Molienda: Grano, Fina" in cafe.caracteristicas, "atributos", cafe.caracteristicas)
    check(cafe.tiempo_entrega == "2 a 4 d\u00edas h\u00e1biles", "entrega desde la PDP", cafe.tiempo_entrega)
prensa = por_sku.get("PF-600")
if prensa:
    check(prensa.disponible == "No" and prensa.inventario == "0", "agotado -> No / 0", f"{prensa.disponible}/{prensa.inventario}")
srv_w.shutdown()

# ---------------------------------------------------------------- resumen
print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron:")
    for f in fallos:
        print("  -", f)
    raise SystemExit(1)
print("Todas las pruebas pasaron.")
