"""Extractor genérico: descubre URLs de producto y lee datos estructurados
(JSON-LD schema.org, microdatos y meta tags de OpenGraph)."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from . import atributos
from .core import Producto, limpiar_html, normalizar_precio, recortar
from .shipping import extraer_tiempo_entrega, politica_envio_del_sitio

# Códigos de unidad de schema.org (UN/CEFACT).
_UNIDAD_LARGO = {"CMT": 1.0, "MMT": 0.1, "MTR": 100.0, "INH": 2.54, "FOT": 30.48}
_UNIDAD_PESO = {"KGM": 1.0, "GRM": 0.001, "LBR": 0.45359, "ONZ": 0.02835}
_TEXTO_LARGO = {"cm": 1.0, "mm": 0.1, "m": 100.0, "in": 2.54, "pulgadas": 2.54, "ft": 30.48}
_TEXTO_PESO = {"kg": 1.0, "g": 0.001, "gr": 0.001, "lb": 0.45359, "oz": 0.02835}

PISTAS_PRODUCTO = re.compile(
    r"/(?:products?|producto?s?|p|item|items|articulo|art[íi]culo|shop|tienda|dp)/[^/?#]{2,}", re.I
)
EXCLUIR = re.compile(r"\.(?:jpg|jpeg|png|gif|webp|svg|pdf|zip|css|js)(?:$|\?)|/(?:cart|carrito|login|cuenta|account|blog|search)/", re.I)

_LD = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
_META = re.compile(r"<meta[^>]+(?:property|name|itemprop)=[\"']([^\"']+)[\"'][^>]*content=[\"']([^\"']*)[\"']", re.I)
_META_INV = re.compile(r"<meta[^>]+content=[\"']([^\"']*)[\"'][^>]*(?:property|name|itemprop)=[\"']([^\"']+)[\"']", re.I)
_LINKS = re.compile(r"<a[^>]+href=[\"']([^\"'#]+)[\"']", re.I)
_TITULO = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


# ---------------------------------------------------------------- sitemaps

def _sitemaps_declarados(fetcher, base: str) -> list[str]:
    urls = []
    r = fetcher.get(base + "/robots.txt")
    if r is not None and r.status_code == 200:
        urls += re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text)
    urls += [
        base + s
        for s in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/product-sitemap.xml", "/wp-sitemap.xml"]
    ]
    vistos, salida = set(), []
    for u in urls:
        if u not in vistos:
            vistos.add(u)
            salida.append(u)
    return salida


def _leer_sitemap(fetcher, url: str, profundidad=0, limite=8000) -> list[str]:
    if profundidad > 2:
        return []
    r = fetcher.get(url)
    if r is None or r.status_code != 200 or "<" not in r.text[:200]:
        return []
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text, re.I)
    if "<sitemapindex" in r.text[:2000].lower():
        salida = []
        # Prioriza sub-sitemaps que suenen a producto.
        locs.sort(key=lambda u: 0 if re.search(r"produc|item|shop|tienda", u, re.I) else 1)
        for sub in locs[:25]:
            salida += _leer_sitemap(fetcher, sub, profundidad + 1, limite)
            if len(salida) >= limite:
                break
        return salida[:limite]
    return locs[:limite]


def descubrir_urls(fetcher, entrada: str, base: str, max_urls: int, progreso=None) -> list[str]:
    dominio = urlparse(base).netloc
    candidatas: list[str] = []

    for sm in _sitemaps_declarados(fetcher, base):
        candidatas += _leer_sitemap(fetcher, sm)
        if progreso:
            progreso(f"Sitemap: {len(candidatas)} URLs encontradas…", None)
        if len(candidatas) >= max_urls * 12:
            break

    productos = [
        u for u in candidatas
        if urlparse(u).netloc == dominio and PISTAS_PRODUCTO.search(u) and not EXCLUIR.search(u)
    ]

    # Si el sitemap no ayudó, sigue los enlaces de la página de entrada.
    if len(productos) < 5:
        for pagina in dict.fromkeys([entrada, base]):
            r = fetcher.get(pagina)
            if r is None or r.status_code != 200:
                continue
            for href in _LINKS.findall(r.text):
                u = urljoin(pagina, href).split("#")[0]
                if urlparse(u).netloc == dominio and PISTAS_PRODUCTO.search(u) and not EXCLUIR.search(u):
                    productos.append(u)

    # Último recurso: cualquier URL interna del sitemap que no sea obviamente institucional.
    if len(productos) < 5:
        productos = [
            u for u in candidatas
            if urlparse(u).netloc == dominio
            and not EXCLUIR.search(u)
            and not re.search(r"/(?:pages?|blog|news|about|contacto|contact|policies|categor)", u, re.I)
        ]

    return list(dict.fromkeys(productos))[:max_urls]


# ------------------------------------------------------------- datos structurados

def _iterar_nodos(data):
    if isinstance(data, dict):
        yield data
        for v in data.values():
            yield from _iterar_nodos(v)
    elif isinstance(data, list):
        for v in data:
            yield from _iterar_nodos(v)


def _es_tipo(nodo: dict, tipo: str) -> bool:
    t = nodo.get("@type")
    if isinstance(t, list):
        return any(str(x).lower() == tipo for x in t)
    return str(t).lower() == tipo


def _nodo_producto(html: str) -> dict | None:
    for bloque in _LD.findall(html):
        bloque = bloque.strip()
        if not bloque:
            continue
        try:
            data = json.loads(bloque)
        except json.JSONDecodeError:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", bloque))
            except json.JSONDecodeError:
                continue
        for nodo in _iterar_nodos(data):
            if isinstance(nodo, dict) and _es_tipo(nodo, "product"):
                return nodo
    return None


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, dict):
        return str(valor.get("name") or valor.get("@id") or valor.get("value") or "")
    if isinstance(valor, list):
        return ", ".join(_texto(v) for v in valor if _texto(v))
    return str(valor)


def _oferta(nodo: dict) -> dict:
    ofertas = nodo.get("offers")
    if isinstance(ofertas, list):
        return next((o for o in ofertas if isinstance(o, dict)), {})
    return ofertas if isinstance(ofertas, dict) else {}


_DISPONIBLE = {
    "instock": "Sí", "in_stock": "Sí", "onlineonly": "Sí", "limitedavailability": "Sí",
    "preorder": "Preventa", "presale": "Preventa", "backorder": "Bajo pedido",
    "outofstock": "No", "soldout": "No", "discontinued": "No",
}


def _disponibilidad(valor) -> str:
    clave = _texto(valor).split("/")[-1].strip().lower().replace(" ", "")
    return _DISPONIBLE.get(clave, "")


def _cantidad(valor, unidades_codigo: dict, unidades_texto: dict) -> str:
    """Convierte height/width/weight de schema.org a cm o kg."""
    if valor in (None, ""):
        return ""
    if isinstance(valor, list):
        valor = valor[0] if valor else None
    if isinstance(valor, dict):
        numero = valor.get("value")
        factor = unidades_codigo.get(str(valor.get("unitCode", "")).upper())
        if factor is None:
            factor = unidades_texto.get(str(valor.get("unitText", "")).lower())
        if factor is None:
            factor = 1.0
    else:
        m = re.match(r"\s*([\d.,]+)\s*([a-zA-Z\"']*)", str(valor))
        if not m:
            return ""
        numero = m.group(1)
        factor = unidades_texto.get(m.group(2).lower(), 1.0)
    try:
        n = float(str(numero).replace(",", "."))
    except (TypeError, ValueError):
        return ""
    resultado = n * factor
    return f"{resultado:.2f}".rstrip("0").rstrip(".")


def _imagenes(nodo: dict, metas: dict) -> list[str]:
    crudo = nodo.get("image")
    urls: list[str] = []
    if isinstance(crudo, str):
        urls = [crudo]
    elif isinstance(crudo, list):
        for x in crudo:
            if isinstance(x, str):
                urls.append(x)
            elif isinstance(x, dict):
                u = x.get("url") or x.get("contentUrl")
                if u:
                    urls.append(u)
    elif isinstance(crudo, dict):
        u = crudo.get("url") or crudo.get("contentUrl")
        if u:
            urls.append(u)
    if metas.get("og:image"):
        urls.append(metas["og:image"])
    limpias = [u.strip() for u in urls if isinstance(u, str) and u.strip().startswith("http")]
    return list(dict.fromkeys(limpias))[:8]


def _metas(html: str) -> dict:
    d = {}
    for k, v in _META.findall(html):
        d.setdefault(k.lower(), v)
    for v, k in _META_INV.findall(html):
        d.setdefault(k.lower(), v)
    return d


def parsear_pagina(html: str, url: str, plataforma: str, fallback_entrega: str = "") -> Producto | None:
    nodo = _nodo_producto(html) or {}
    metas = _metas(html)
    oferta = _oferta(nodo)

    nombre = _texto(nodo.get("name")) or metas.get("og:title", "")
    if not nombre:
        m = _TITULO.search(html)
        nombre = limpiar_html(m.group(1)) if m else ""
    nombre = limpiar_html(nombre)

    spec = oferta.get("priceSpecification")
    spec = spec if isinstance(spec, dict) else {}
    precio = normalizar_precio(oferta.get("price") or oferta.get("lowPrice") or spec.get("price"))
    if not precio:
        precio = normalizar_precio(metas.get("product:price:amount") or metas.get("og:price:amount") or metas.get("price"))

    moneda = (
        _texto(oferta.get("priceCurrency"))
        or _texto(spec.get("priceCurrency"))
        or metas.get("product:price:currency", "")
        or metas.get("og:price:currency", "")
    )

    disponible = _disponibilidad(oferta.get("availability")) or _disponibilidad(metas.get("product:availability") or metas.get("availability"))

    inventario = ""
    for clave in ("inventoryLevel", "inventory_level"):
        v = oferta.get(clave) or nodo.get(clave)
        if isinstance(v, dict):
            v = v.get("value")
        if v not in (None, ""):
            inventario = str(v)
            break
    if not inventario:
        m = re.search(r"(?:quedan|solo\s+quedan|s[óo]lo\s+quedan|only)\s+(\d{1,4})\s+(?:en\s+)?(?:piezas?|unidades?|left|disponibles?)", html, re.I)
        if m:
            inventario = m.group(1)
    if not inventario and disponible == "No":
        inventario = "0"

    caracteristicas = []
    for prop in nodo.get("additionalProperty", []) or []:
        if isinstance(prop, dict):
            n, v = _texto(prop.get("name")), _texto(prop.get("value"))
            if n and v:
                caracteristicas.append(f"{n}: {v}")
    for campo, etiqueta in [("color", "Color"), ("material", "Material"), ("size", "Tamaño"), ("weight", "Peso"), ("model", "Modelo")]:
        v = _texto(nodo.get(campo))
        if v:
            caracteristicas.append(f"{etiqueta}: {v}")

    descripcion = limpiar_html(_texto(nodo.get("description")) or metas.get("og:description", ""))

    if not nombre and not precio:
        return None

    imagenes = _imagenes(nodo, metas)

    producto = Producto(
        nombre=nombre,
        variante="",
        sku=_texto(nodo.get("sku")) or _texto(nodo.get("mpn")) or _texto(oferta.get("sku")),
        marca=_texto(nodo.get("brand")),
        categoria=_texto(nodo.get("category")),
        precio=precio,
        precio_lista=normalizar_precio(nodo.get("highPrice") or oferta.get("highPrice")),
        moneda=moneda,
        disponible=disponible,
        inventario=inventario,
        tiempo_entrega=extraer_tiempo_entrega(html) or fallback_entrega,
        color=_texto(nodo.get("color")),
        material=_texto(nodo.get("material")),
        alto_cm=_cantidad(nodo.get("height"), _UNIDAD_LARGO, _TEXTO_LARGO),
        ancho_cm=_cantidad(nodo.get("width"), _UNIDAD_LARGO, _TEXTO_LARGO),
        largo_cm=_cantidad(nodo.get("length"), _UNIDAD_LARGO, _TEXTO_LARGO),
        profundidad_cm=_cantidad(nodo.get("depth"), _UNIDAD_LARGO, _TEXTO_LARGO),
        peso_kg=_cantidad(nodo.get("weight"), _UNIDAD_PESO, _TEXTO_PESO),
        caracteristicas=" | ".join(caracteristicas),
        descripcion=recortar(descripcion),
        imagen=imagenes[0] if imagenes else "",
        imagenes=", ".join(imagenes),
        url_producto=url,
        plataforma=plataforma,
    )
    atributos.enriquecer(producto, limpiar_html(html)[:12000])
    return producto


def _prefiltrar_urls(urls: list[str], filtro, progreso=None) -> list[str]:
    """Descarta URLs cuyo slug no menciona ningún término del filtro.
    Solo se usa si deja suficientes candidatas, para no perder productos
    cuya URL es un número o un código."""
    if filtro is None or not filtro.terminos_sueltos:
        return urls
    candidatas = [u for u in urls if filtro.texto_coincide_parcial(u.rsplit("/", 2)[-1].replace("-", " "))]
    if len(candidatas) >= 3:
        if progreso:
            progreso(f"Filtro por URL: {len(candidatas)} candidatas de {len(urls)}", 0.15)
        return candidatas
    return urls


def scrape(
    fetcher,
    entrada: str,
    base: str,
    *,
    max_productos=300,
    workers=4,
    filtro=None,
    prefiltrar_urls=True,
    progreso=None,
    plataforma="Genérico",
) -> list[Producto]:
    # Se descubre un margen extra de URLs porque el filtro descartará muchas.
    tope = max_productos * 8 if (filtro is not None and filtro.activo) else max_productos
    urls = descubrir_urls(fetcher, entrada, base, min(tope, 6000), progreso)
    if not urls:
        return []

    if prefiltrar_urls:
        urls = _prefiltrar_urls(urls, filtro, progreso)
    urls = urls[: max(max_productos, 1) * (6 if (filtro is not None and filtro.activo) else 1)]

    fallback_entrega = politica_envio_del_sitio(fetcher, base)
    filas: list[Producto] = []
    hechos = 0

    def trabajo(url):
        r = fetcher.get(url, allow_cache=False)
        if r is None or r.status_code != 200:
            return None
        return parsear_pagina(r.text, url, plataforma, fallback_entrega)

    # Se procesa por tandas para poder parar en cuanto se junten suficientes.
    n = max(1, workers)
    tanda = n * 4
    with ThreadPoolExecutor(max_workers=n) as pool:
        for inicio in range(0, len(urls), tanda):
            for resultado in pool.map(trabajo, urls[inicio : inicio + tanda]):
                hechos += 1
                if resultado and (filtro is None or filtro.coincide(resultado)):
                    filas.append(resultado)
            if progreso:
                progreso(f"Leyendo fichas: {hechos}/{len(urls)} ({len(filas)} coinciden)", hechos / len(urls))
            if len(filas) >= max_productos:
                break

    return filas[:max_productos]
