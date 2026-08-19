"""Extractor para tiendas WooCommerce vía la Store API pública."""

from __future__ import annotations

from . import atributos
from .core import Producto, limpiar_html, normalizar_precio, recortar
from .shipping import extraer_tiempo_entrega, politica_envio_del_sitio

ENDPOINTS = ["/wp-json/wc/store/v1/products", "/wp-json/wc/store/products"]


def _detectar_endpoint(fetcher, base: str) -> str | None:
    for ep in ENDPOINTS:
        data = fetcher.get_json(base + ep, params={"per_page": 1})
        if isinstance(data, list):
            return ep
    return None


def es_woocommerce(fetcher, base: str) -> bool:
    return _detectar_endpoint(fetcher, base) is not None


def _precio(valor, minor_unit) -> str:
    """La Store API devuelve enteros escalados: 1999 con minor_unit=2 -> 19.99."""
    if valor in (None, ""):
        return ""
    try:
        return f"{int(valor) / (10 ** int(minor_unit or 0)):.2f}"
    except (ValueError, TypeError):
        return normalizar_precio(valor)


def _caracteristicas(prod: dict) -> str:
    partes = []
    for attr in prod.get("attributes", []) or []:
        nombre = attr.get("name", "")
        terminos = ", ".join(t.get("name", "") for t in attr.get("terms", []) or [])
        if nombre and terminos:
            partes.append(f"{nombre}: {terminos}")
    corta = limpiar_html(prod.get("short_description", ""))
    if corta:
        partes.append(recortar(corta, 300))
    return " | ".join(partes)


def scrape(fetcher, base: str, *, max_productos=1000, detalle_inventario=True, filtro=None, progreso=None) -> list[Producto]:
    ep = _detectar_endpoint(fetcher, base)
    if not ep:
        return []

    # ---- fase 1: catálogo
    filas: list[Producto] = []
    pagina = 1
    while len(filas) < max_productos and pagina <= 60:
        lote = fetcher.get_json(base + ep, params={"per_page": 100, "page": pagina})
        if not isinstance(lote, list) or not lote:
            break

        for prod in lote:
            precios = prod.get("prices", {}) or {}
            mu = precios.get("currency_minor_unit", 2)
            en_stock = prod.get("is_in_stock")
            inv = prod.get("low_stock_remaining")
            if inv is None and en_stock is False:
                inv = 0
            imagenes = [i.get("src", "") for i in prod.get("images", []) or [] if i.get("src")]

            p = Producto(
                nombre=prod.get("name", ""),
                variante=", ".join(
                    f"{v.get('attribute','')}: {v.get('value','')}" for v in prod.get("variation", []) or []
                ),
                sku=prod.get("sku", "") or "",
                categoria=", ".join(c.get("name", "") for c in prod.get("categories", []) or []),
                precio=_precio(precios.get("price"), mu),
                precio_lista=_precio(precios.get("regular_price"), mu),
                moneda=precios.get("currency_code", "") or "",
                disponible="Sí" if en_stock else ("No" if en_stock is False else ""),
                inventario="" if inv is None else str(inv),
                caracteristicas=_caracteristicas(prod),
                descripcion=recortar(limpiar_html(prod.get("description", ""))),
                imagen=imagenes[0] if imagenes else "",
                imagenes=", ".join(imagenes[:8]),
                url_producto=prod.get("permalink", "") or base,
                plataforma="WooCommerce",
            )
            atributos.enriquecer(p)
            filas.append(p)

        if progreso:
            progreso(f"WooCommerce: {len(filas)} productos en el catálogo…", 0.15)
        if len(lote) < 100:
            break
        pagina += 1

    filas = filas[:max_productos]

    # ---- fase 2: filtro
    if filtro is not None and filtro.activo:
        antes = len(filas)
        filas = filtro.aplicar(filas)
        if progreso:
            progreso(f"Filtro: {len(filas)} de {antes} coinciden", 0.25)

    if not filas or not detalle_inventario:
        return filas

    # ---- fase 3: entrega y medidas de la ficha
    fallback_entrega = politica_envio_del_sitio(fetcher, base)
    for i, p in enumerate(filas):
        r = fetcher.get(p.url_producto) if p.url_producto else None
        if r is not None and r.status_code == 200:
            p.tiempo_entrega = extraer_tiempo_entrega(r.text) or fallback_entrega
            atributos.enriquecer(p, limpiar_html(r.text)[:12000])
        else:
            p.tiempo_entrega = fallback_entrega
        if progreso:
            progreso(f"Detalle {i + 1}/{len(filas)}", 0.3 + 0.7 * (i + 1) / max(len(filas), 1))

    return filas
