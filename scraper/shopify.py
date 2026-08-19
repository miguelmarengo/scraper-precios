"""Extractor para tiendas Shopify usando los endpoints JSON públicos.

Trabaja en dos fases: primero arma el catálogo con una sola llamada por página,
y solo después de aplicar el filtro abre la ficha de los productos que sobreviven.
"""

from __future__ import annotations

import re
from collections import defaultdict

from . import atributos
from .core import Producto, limpiar_html, normalizar_precio, recortar
from .shipping import extraer_tiempo_entrega, politica_envio_del_sitio

_A_KG = {"kg": 1.0, "g": 0.001, "lb": 0.45359, "oz": 0.02835}


def _moneda(fetcher, base: str) -> str:
    r = fetcher.get(base + "/")
    if r is None or r.status_code != 200:
        return ""
    for rx in [r"Shopify\.currency\s*=\s*\{[^}]*\"active\"\s*:\s*\"([A-Z]{3})\"", r"\"currencyCode\"\s*:\s*\"([A-Z]{3})\""]:
        m = re.search(rx, r.text)
        if m:
            return m.group(1)
    return ""


def _caracteristicas(prod: dict, variante: dict) -> str:
    partes = []
    nombres = [o.get("name", "") for o in prod.get("options", []) or []]
    valores = [variante.get(f"option{i}") for i in (1, 2, 3)]
    for n, v in zip(nombres, valores):
        if n and v and v != "Default Title":
            partes.append(f"{n}: {v}")
    if variante.get("barcode"):
        partes.append(f"Código de barras: {variante['barcode']}")
    if prod.get("tags"):
        tags = prod["tags"]
        tags = ", ".join(tags) if isinstance(tags, list) else str(tags)
        if tags.strip():
            partes.append(f"Etiquetas: {tags}")
    return " | ".join(partes)


def _peso(variante: dict) -> str:
    peso, unidad = variante.get("weight"), (variante.get("weight_unit") or "g").lower()
    if peso in (None, "", 0):
        return ""
    factor = _A_KG.get(unidad)
    if not factor:
        return ""
    try:
        kg = float(peso) * factor
    except (TypeError, ValueError):
        return ""
    if kg <= 0:
        return ""
    return f"{kg:.3f}".rstrip("0").rstrip(".")


def es_shopify(fetcher, base: str) -> bool:
    data = fetcher.get_json(base + "/products.json", params={"limit": 1})
    return isinstance(data, dict) and "products" in data


def scrape(fetcher, base: str, *, max_productos=1000, detalle_inventario=True, filtro=None, progreso=None) -> list[Producto]:
    moneda = _moneda(fetcher, base)

    # ---- fase 1: catálogo completo, barato
    crudos: list[dict] = []
    pagina = 1
    while len(crudos) < max_productos and pagina <= 60:
        data = fetcher.get_json(base + "/products.json", params={"limit": 250, "page": pagina})
        lote = (data or {}).get("products") or []
        if not lote:
            break
        crudos.extend(lote)
        if progreso:
            progreso(f"Shopify: {len(crudos)} productos en el catálogo…", 0.15)
        if len(lote) < 250:
            break
        pagina += 1

    crudos = crudos[:max_productos]
    filas: list[Producto] = []
    por_handle: dict[str, list[Producto]] = defaultdict(list)
    id_variante: dict[int, Producto] = {}

    for prod in crudos:
        handle = prod.get("handle", "")
        url_prod = f"{base}/products/{handle}" if handle else base
        descripcion = recortar(limpiar_html(prod.get("body_html", "")))
        imagenes = [i.get("src", "") for i in prod.get("images", []) or [] if i.get("src")]

        for variante in prod.get("variants", []) or []:
            disponible = variante.get("available")
            imagen_var = (variante.get("featured_image") or {}).get("src") if isinstance(variante.get("featured_image"), dict) else None
            p = Producto(
                nombre=prod.get("title", ""),
                variante="" if variante.get("title") in (None, "Default Title") else variante.get("title", ""),
                sku=variante.get("sku", "") or "",
                marca=prod.get("vendor", "") or "",
                categoria=prod.get("product_type", "") or "",
                precio=normalizar_precio(variante.get("price")),
                precio_lista=normalizar_precio(variante.get("compare_at_price")),
                moneda=moneda,
                disponible="Sí" if disponible else ("No" if disponible is False else ""),
                inventario="0" if disponible is False else "",
                peso_kg=_peso(variante),
                caracteristicas=_caracteristicas(prod, variante),
                descripcion=descripcion,
                imagen=imagen_var or (imagenes[0] if imagenes else ""),
                imagenes=", ".join(imagenes[:8]),
                url_producto=url_prod,
                plataforma="Shopify",
            )
            atributos.enriquecer(p)
            filas.append(p)
            por_handle[handle].append(p)
            if variante.get("id") is not None:
                id_variante[variante["id"]] = p

    # ---- fase 2: filtrar antes de gastar peticiones
    if filtro is not None and filtro.activo:
        antes = len(filas)
        filas = filtro.aplicar(filas)
        if progreso:
            progreso(f"Filtro: {len(filas)} de {antes} coinciden", 0.25)
        vivos = {id(p) for p in filas}
        por_handle = {h: [p for p in ps if id(p) in vivos] for h, ps in por_handle.items()}
        por_handle = {h: ps for h, ps in por_handle.items() if ps}

    if not filas or not detalle_inventario:
        return filas

    # ---- fase 3: inventario, entrega y medidas solo de lo que quedó
    fallback_entrega = politica_envio_del_sitio(fetcher, base)
    handles = list(por_handle)
    for i, handle in enumerate(handles):
        det = fetcher.get_json(f"{base}/products/{handle}.js")
        if isinstance(det, dict):
            for v in det.get("variants", []) or []:
                p = id_variante.get(v.get("id"))
                qty = v.get("inventory_quantity")
                if p is not None and qty is not None and v.get("inventory_management"):
                    p.inventario = str(qty)

        texto_pdp = ""
        entrega = ""
        r = fetcher.get(f"{base}/products/{handle}")
        if r is not None and r.status_code == 200:
            entrega = extraer_tiempo_entrega(r.text)
            texto_pdp = limpiar_html(r.text)[:12000]

        for p in por_handle[handle]:
            p.tiempo_entrega = entrega or fallback_entrega
            atributos.enriquecer(p, texto_pdp)

        if progreso:
            progreso(f"Detalle {i + 1}/{len(handles)}", 0.3 + 0.7 * (i + 1) / max(len(handles), 1))

    return filas
