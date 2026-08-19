"""Orquestador: detecta la plataforma y ejecuta el extractor adecuado."""

from __future__ import annotations

import re
from datetime import datetime

from . import generic, shopify, woocommerce
from .core import COLUMNS, Fetcher, Producto, base_url, normalizar_url_entrada
from .filtro import Filtro


def detectar_plataforma(fetcher: Fetcher, base: str) -> str:
    if shopify.es_shopify(fetcher, base):
        return "Shopify"
    if woocommerce.es_woocommerce(fetcher, base):
        return "WooCommerce"

    r = fetcher.get(base + "/")
    html = r.text[:200000] if (r is not None and r.status_code == 200) else ""
    if re.search(r"cdn\.shopify\.com|Shopify\.theme", html):
        return "Shopify (sin API pública)"
    if re.search(r"wp-content/plugins/woocommerce|woocommerce-", html, re.I):
        return "WooCommerce (sin API pública)"
    if re.search(r"vtex(?:assets|commercestable)|__RUNTIME__", html, re.I):
        return "VTEX"
    if re.search(r"Magento|mage/|magento_", html):
        return "Magento"
    if re.search(r"\.squarespace\.com|Static\.SQUARESPACE", html, re.I):
        return "Squarespace"
    if re.search(r"wixstatic\.com|X-Wix", html, re.I):
        return "Wix"
    if re.search(r"tiendanube|nuvemshop", html, re.I):
        return "Tiendanube"
    if re.search(r"bigcommerce", html, re.I):
        return "BigCommerce"
    return "Genérico"


def scrapear(
    url: str,
    *,
    filtro: str | Filtro = "",
    precio_min: float | None = None,
    precio_max: float | None = None,
    solo_disponibles: bool = False,
    max_productos: int = 300,
    detalle_inventario: bool = True,
    respetar_robots: bool = True,
    delay: float = 0.6,
    workers: int = 4,
    prefiltrar_urls: bool = True,
    progreso=None,
) -> tuple[list[Producto], dict]:
    """Devuelve (productos, informe)."""
    if isinstance(filtro, Filtro):
        f = filtro
    else:
        f = Filtro(filtro, precio_min=precio_min, precio_max=precio_max, solo_disponibles=solo_disponibles)

    entrada = normalizar_url_entrada(url)
    if not entrada:
        raise ValueError("Escribe una URL válida.")
    base = base_url(entrada)

    fetcher = Fetcher(delay=delay, respetar_robots=respetar_robots)

    if not fetcher.permitido(entrada):
        raise PermissionError(
            "El archivo robots.txt de este sitio no permite el rastreo automatizado de esa ruta. "
            "Puedes desactivar la casilla 'Respetar robots.txt' bajo tu propia responsabilidad."
        )

    def paso(msg, pct=None):
        if progreso:
            progreso(msg, pct)

    paso("Detectando la plataforma…", 0.02)
    plataforma = detectar_plataforma(fetcher, base)
    paso(f"Plataforma detectada: {plataforma}", 0.06)

    def generico():
        return generic.scrape(
            fetcher,
            entrada,
            base,
            max_productos=max_productos,
            workers=workers,
            filtro=f,
            prefiltrar_urls=prefiltrar_urls,
            progreso=progreso,
            plataforma=plataforma,
        )

    if plataforma == "Shopify":
        productos = shopify.scrape(
            fetcher, base, max_productos=max_productos, detalle_inventario=detalle_inventario,
            filtro=f, progreso=progreso,
        )
    elif plataforma == "WooCommerce":
        productos = woocommerce.scrape(
            fetcher, base, max_productos=max_productos, detalle_inventario=detalle_inventario,
            filtro=f, progreso=progreso,
        )
    else:
        productos = generico()

    # Si el atajo de la plataforma no dio nada, intenta el camino genérico.
    if not productos and plataforma in ("Shopify", "WooCommerce") and not f.activo:
        paso("La API de la plataforma no devolvió datos; probando el método genérico…", 0.3)
        productos = generico()

    # Una sola fecha y hora para toda la corrida (no una por producto, que podría
    # variar por segundos según cuándo se leyó cada ficha) — así, si alguien necesita
    # el CSV en lugar de la hoja de Google, sabe exactamente cuándo se hizo esta extracción.
    corrida = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    for p in productos:
        p.fecha_extraccion = corrida

    informe = {
        "corrida": corrida,
        "url": entrada,
        "plataforma": plataforma,
        "filtro": f.consulta,
        "filtro_activo": f.activo,
        # Si nunca llegó ni una sola respuesta real del sitio, el problema no es el
        # filtro: es que algo (login, bloqueo anti-robots, JavaScript) nos está
        # cerrando el paso antes de ver el catálogo.
        "conexion_bloqueada": fetcher.sin_ninguna_respuesta(),
        "detalle_error": fetcher.ultimo_error,
        # Distinto del caso anterior: aquí ni siquiera lo intentamos, porque el propio
        # robots.txt de la tienda lo prohíbe y tenemos "Respetar robots.txt" activado.
        # Es la causa más común de "corrió un segundo y no trajo nada".
        "bloqueado_por_robots": fetcher.bloqueado_por_robots(),
        "bloqueos_robots": fetcher.bloqueados_por_robots,
        "filas": len(productos),
        "con_precio": sum(1 for p in productos if p.precio),
        "con_foto": sum(1 for p in productos if p.imagen),
        "con_inventario": sum(1 for p in productos if p.inventario != ""),
        "con_entrega": sum(1 for p in productos if p.tiempo_entrega),
        "con_medidas": sum(1 for p in productos if p.alto_cm or p.ancho_cm or p.largo_cm or p.dimensiones),
        "columnas": COLUMNS,
    }
    return productos, informe


def a_tabla(productos: list[Producto]) -> list[list]:
    return [COLUMNS] + [p.as_row() for p in productos]
