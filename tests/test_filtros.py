"""Pruebas del filtro, la extracción de atributos y las fotos."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fixture_server import arrancar  # noqa: E402

from scraper import Filtro, scrapear  # noqa: E402
from scraper.atributos import enriquecer  # noqa: E402
from scraper.core import Producto  # noqa: E402
from scraper.filtro import formas  # noqa: E402

fallos = []


def check(cond, etiqueta, extra=""):
    print(("  ok   " if cond else "  FALLA") + f"  {etiqueta}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        fallos.append(etiqueta)


# ------------------------------------------------------------ singularización
print("\n[1] Plurales y género")
for palabra, esperado in [("sillones", "sillon"), ("blancos", "blanco"), ("verdes", "verde"),
                          ("mesas", "mesa"), ("luces", "luz"), ("colores", "color"),
                          ("papeles", "papel"), ("sofa", "sofa"), ("gris", "gris")]:
    got = formas(palabra)
    check(esperado in got, f"formas({palabra}) incluye {esperado}", str(got))
check({"blanco", "blanca"} <= formas("blancos"), "variantes de género", str(formas("blancos")))
check("verde" in formas("verdes") and "verd" in formas("verdes"),
      "plural ambiguo conserva las dos lecturas", str(formas("verdes")))

# ------------------------------------------------------------ coincidencias
print("\n[2] Coincidencia de texto")
casos = [
    ("sillones blancos", "Sillón Oslo blanca de lino", True),
    ("sillones blancos", "Sillón Oslo negro de lino", False),
    ("verduras verdes", "Verdura verde de temporada", True),
    ("verduras verdes", "Verdura roja de temporada", False),
    ("sillon | sofa", "Sofá cama de 3 plazas", True),
    ("sillon | sofa", "Mesa de centro", False),
    ('"sofa cama"', "Sofá cama de 3 plazas", True),
    ('"sofa cama"', "Sofá esquinero y cama aparte", False),
    ("sillones -piel", "Sillón de piel negra", False),
    ("sillones -piel", "Sillón de lino negro", True),
    ("", "Cualquier cosa", True),
    ("MESA", "mesa de roble", True),
    ("cafe", "Café de altura", True),
]
for consulta, texto, esperado in casos:
    got = Filtro(consulta).texto_coincide(texto)
    check(got == esperado, f"{consulta!r} vs {texto!r} -> {esperado}", str(got))

print("\n[3] Filtros numéricos")
p = Producto(nombre="Silla", precio="500.00", disponible="No")
check(Filtro("", precio_min=100, precio_max=1000).coincide(p), "dentro del rango")
check(not Filtro("", precio_min=600).coincide(p), "por debajo del mínimo")
check(not Filtro("", precio_max=400).coincide(p), "por encima del máximo")
check(not Filtro("", solo_disponibles=True).coincide(p), "agotado se descarta")
check(Filtro("").activo is False, "filtro vacío está inactivo")

# ------------------------------------------------------------ atributos
print("\n[4] Extracción de atributos")
p = Producto(nombre="Mesa Nórdica", descripcion="Mesa de roble macizo. Medidas: 120 x 60 x 75 cm. "
                                                "Peso: 24.5 kg. Garantía de 3 años. Color blanco.")
enriquecer(p)
check(p.largo_cm == "120", "largo del combo", p.largo_cm)
check(p.ancho_cm == "60", "ancho del combo", p.ancho_cm)
check(p.alto_cm == "75", "alto del combo", p.alto_cm)
check(p.peso_kg == "24.5", "peso en kg", p.peso_kg)
check(p.garantia == "3 años", "garantía", p.garantia)
check("roble" in p.material, "material", p.material)
check("blanco" in p.color, "color", p.color)

p2 = Producto(nombre="Repisa", descripcion="Altura 1.2 m, ancho 800 mm, profundidad 12 pulgadas. Pesa 3500 g.")
enriquecer(p2)
check(p2.alto_cm == "120", "metros -> cm", p2.alto_cm)
check(p2.ancho_cm == "80", "milímetros -> cm", p2.ancho_cm)
check(p2.profundidad_cm == "30.48", "pulgadas -> cm", p2.profundidad_cm)
check(p2.peso_kg == "3.5", "gramos -> kg", p2.peso_kg)

p3 = Producto(nombre="Termo", descripcion="Capacidad de 750 ml. Acero inoxidable.")
enriquecer(p3)
check(p3.capacidad == "750 ml", "capacidad", p3.capacidad)
check("acero" in p3.material, "material acero", p3.material)

p4 = Producto(nombre="Oferta", precio="750.00", precio_lista="1000.00")
enriquecer(p4)
check(p4.descuento_pct == "25", "descuento calculado", p4.descuento_pct)

p5 = Producto(nombre="Sin oferta", precio="1000.00", precio_lista="")
enriquecer(p5)
check(p5.descuento_pct == "", "sin precio de lista no hay descuento", p5.descuento_pct)

# ------------------------------------------------------------ fotos
print("\n[5] Fotos")
p6 = Producto(nombre="X", imagen="https://cdn.test/a.jpg")
check(p6.foto == '=IMAGE("https://cdn.test/a.jpg")', "fórmula IMAGE()", p6.foto)
check(Producto(nombre="X").foto == "", "sin imagen no hay fórmula")

# ------------------------------------------------------------ integración
print("\n[6] Filtro sobre una tienda Shopify real (simulada)")
srv, url = arrancar(modo="shopify")
prods, informe = scrapear(url, filtro="sillones blancos", delay=0.0, workers=2)
check(len(prods) == 1, "solo la variante blanca", str([p.sku for p in prods]))
if prods:
    s = prods[0]
    check(s.sku == "SO-BL", "sku correcto", s.sku)
    check(s.descuento_pct == "19", "descuento 15999 -> 12999", s.descuento_pct)
    check(s.peso_kg == "18", "peso de la variante Shopify", s.peso_kg)
    check(s.largo_cm == "75" and s.ancho_cm == "80" and s.alto_cm == "90", "medidas del combo",
          f"{s.largo_cm}/{s.ancho_cm}/{s.alto_cm}")
    check(s.garantia == "2 años", "garantía", s.garantia)
    check(s.color.lower() == "blanco", "color", s.color)
    check("lino" in s.material, "material lino", s.material)
    check(s.imagen == "https://cdn.test/sillon-1.jpg", "foto principal", s.imagen)
    check(s.imagenes.count(",") == 1, "dos fotos en la lista", s.imagenes)
    check(s.inventario == "3", "inventario de la variante", s.inventario)
    check(s.foto.startswith("=IMAGE("), "columna foto", s.foto)

# El filtro debe evitar abrir las fichas que no interesan.
detalles = [r for r in srv.peticiones if r.startswith("/products/") and not r.endswith(".js")]
check(all("sillon-oslo" in d for d in detalles), "solo se abrió la ficha filtrada", str(set(detalles)))
srv.shutdown()

print("\n[7] Filtro que no encuentra nada")
srv2, url2 = arrancar(modo="shopify")
prods, informe = scrapear(url2, filtro="bicicletas", delay=0.0, workers=2)
check(prods == [], "sin resultados", str(len(prods)))
check(informe["filtro_activo"] is True, "el informe marca el filtro activo")
srv2.shutdown()

print("\n[8] Atributos de schema.org en tienda genérica")
srv3, url3 = arrancar(modo="generico")
prods, informe = scrapear(url3, filtro="silla", delay=0.0, workers=2)
check(len(prods) == 1, "solo la silla", str([p.nombre for p in prods]))
if prods:
    s = prods[0]
    check(s.alto_cm == "85", "height en mm -> cm", s.alto_cm)
    check(s.ancho_cm == "46", "width en cm", s.ancho_cm)
    check(s.profundidad_cm == "50", "depth en cm", s.profundidad_cm)
    check(s.peso_kg == "6.5", "weight en gramos -> kg", s.peso_kg)
    check(s.imagenes.count("http") == 3, "imágenes de JSON-LD + og:image", s.imagenes)
    check(s.imagen == "https://cdn.test/SN-001-1.jpg", "la principal viene de JSON-LD", s.imagen)
    check(s.precio_lista == "2373.75" and s.descuento_pct == "20", "highPrice y descuento",
          f"{s.precio_lista}/{s.descuento_pct}")
srv3.shutdown()

print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron:")
    for f in fallos:
        print("  -", f)
    raise SystemExit(1)
print("Todas las pruebas pasaron.")
