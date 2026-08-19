"""Heurísticas para encontrar el tiempo de entrega declarado en una página."""

from __future__ import annotations

import re

from .core import limpiar_html

# Patrones ordenados de más específico a más general.
_CLAVE = r"(?:entrega|entregamos|env[íi]o|env[íi]os|enviamos|rec[íi]be(?:lo)?|recibir|llega|despacho|plazo)"

PATRONES = [
    _CLAVE + r"[^.<>{}]{0,60}?\b(\d{1,2}\s*(?:a|-|–|y)\s*\d{1,2})\s*d[íi]as?\s*(?:h[áa]biles?|laborables?)?",
    r"\b(\d{1,2}\s*(?:a|-|–|y)\s*\d{1,2})\s*d[íi]as?\s*(?:h[áa]biles?|laborables?)\b",
    _CLAVE + r"[^.<>{}]{0,60}?\b(\d{1,2})\s*d[íi]as?\s*(?:h[áa]biles?|laborables?)?",
    r"\b(\d{1,2})\s*d[íi]as?\s*(?:h[áa]biles?|laborables?)\b",
    r"\b(\d{1,2}\s*(?:a|-|–|to)\s*\d{1,2})\s*business\s*days\b",
    r"\b(\d{1,2})\s*business\s*days\b",
    r"(entrega\s+(?:el\s+)?mismo\s+d[íi]a)",
    r"(env[íi]o\s+(?:el\s+)?mismo\s+d[íi]a)",
    r"(entrega\s+inmediata)",
    r"(disponible\s+para\s+recoger\s+hoy)",
    r"(next[- ]day\s+delivery)",
    r"(same[- ]day\s+delivery)",
]

_COMPILADOS = [re.compile(p, re.I) for p in PATRONES]

# Zonas del HTML donde suele vivir la promesa de entrega.
_BLOQUES = re.compile(
    r"<[^>]+(?:class|id)=[\"'][^\"']*(?:ship|deliver|envio|env%C3%ADo|entrega|logist|plazo)[^\"']*[\"'][^>]*>(.{0,1200}?)</",
    re.I | re.S,
)


def _buscar(texto: str) -> str:
    if not texto:
        return ""
    for rx in _COMPILADOS:
        m = rx.search(texto)
        if m:
            frag = m.group(1).strip()
            frag = re.sub(r"\s+", " ", frag)
            if re.match(r"^\d", frag):
                sufijo = "días hábiles" if re.search(r"h[áa]biles?|laborables?|business", m.group(0), re.I) else "días"
                return f"{frag} {sufijo}"
            return frag.capitalize()
    return ""


def extraer_tiempo_entrega(html: str) -> str:
    """Busca primero en bloques relacionados con envío, luego en toda la página."""
    if not html:
        return ""
    for bloque in _BLOQUES.findall(html)[:12]:
        r = _buscar(limpiar_html(bloque))
        if r:
            return r
    return _buscar(limpiar_html(html)[:20000])


def politica_envio_del_sitio(fetcher, base: str) -> str:
    """Última red: revisa las páginas de política de envío de la tienda."""
    rutas = [
        "/policies/shipping-policy",
        "/pages/shipping",
        "/pages/envios",
        "/envios",
        "/shipping",
        "/pages/politica-de-envios",
    ]
    for ruta in rutas:
        r = fetcher.get(base + ruta)
        if r is not None and r.status_code == 200 and len(r.text) > 500:
            encontrado = extraer_tiempo_entrega(r.text)
            if encontrado:
                return f"{encontrado} (política del sitio)"
    return ""
