"""Núcleo compartido: sesión HTTP, respeto a robots.txt y modelo de producto."""

from __future__ import annotations

import html as html_lib
import re
import time
import threading
import urllib.robotparser as robotparser
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 PriceScraper/1.0"
)

DEFAULT_TIMEOUT = 25

# Campos que van a la hoja, en este orden.
COLUMNS = [
    "foto",
    "nombre",
    "variante",
    "sku",
    "marca",
    "categoria",
    "precio",
    "precio_lista",
    "descuento_pct",
    "moneda",
    "disponible",
    "inventario",
    "tiempo_entrega",
    "color",
    "material",
    "alto_cm",
    "ancho_cm",
    "largo_cm",
    "profundidad_cm",
    "diametro_cm",
    "peso_kg",
    "capacidad",
    "dimensiones",
    "garantia",
    "caracteristicas",
    "descripcion",
    "imagen",
    "imagenes",
    "url_producto",
    "plataforma",
    "fecha_extraccion",
]

# Columnas numéricas, para que Sheets no las trate como texto.
COLUMNAS_NUMERICAS = {
    "precio", "precio_lista", "descuento_pct", "inventario",
    "alto_cm", "ancho_cm", "largo_cm", "profundidad_cm", "diametro_cm", "peso_kg",
}


@dataclass
class Producto:
    nombre: str = ""
    variante: str = ""
    sku: str = ""
    marca: str = ""
    categoria: str = ""
    precio: str = ""
    precio_lista: str = ""
    descuento_pct: str = ""
    moneda: str = ""
    disponible: str = ""
    inventario: str = ""
    tiempo_entrega: str = ""
    color: str = ""
    material: str = ""
    alto_cm: str = ""
    ancho_cm: str = ""
    largo_cm: str = ""
    profundidad_cm: str = ""
    diametro_cm: str = ""
    peso_kg: str = ""
    capacidad: str = ""
    dimensiones: str = ""
    garantia: str = ""
    caracteristicas: str = ""
    descripcion: str = ""
    imagen: str = ""
    imagenes: str = ""
    url_producto: str = ""
    plataforma: str = ""
    fecha_extraccion: str = field(
        default_factory=lambda: datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    )

    @property
    def foto(self) -> str:
        """Fórmula que hace que Google Sheets muestre la miniatura en la celda."""
        url = (self.imagen or "").replace('"', "")
        return f'=IMAGE("{url}")' if url.startswith("http") else ""

    def texto_busqueda(self) -> str:
        return " | ".join(
            x for x in [
                self.nombre, self.variante, self.marca, self.categoria,
                self.color, self.material, self.caracteristicas, self.descripcion,
            ] if x
        )

    def as_row(self) -> list:
        d = asdict(self)
        d["foto"] = self.foto
        return [d.get(c, "") for c in COLUMNS]


class Fetcher:
    """Cliente HTTP educado: un solo user-agent, pausa entre peticiones,
    caché en memoria y verificación de robots.txt."""

    def __init__(self, delay: float = 0.6, respetar_robots: bool = True, timeout: int = DEFAULT_TIMEOUT):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"})
        self.delay = delay
        self.timeout = timeout
        self.respetar_robots = respetar_robots
        self._last = 0.0
        self._lock = threading.Lock()
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._cache: dict[str, requests.Response | None] = {}

    # -- robots -------------------------------------------------------
    def _robots_for(self, url: str):
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if base not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                r = self.session.get(urljoin(base, "/robots.txt"), timeout=10)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                else:
                    rp = None
            except Exception:
                rp = None
            self._robots[base] = rp
        return self._robots[base]

    def permitido(self, url: str) -> bool:
        if not self.respetar_robots:
            return True
        rp = self._robots_for(url)
        if rp is None:
            return True
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:
            return True

    # -- peticiones ---------------------------------------------------
    def _throttle(self):
        with self._lock:
            espera = self.delay - (time.time() - self._last)
            if espera > 0:
                time.sleep(espera)
            self._last = time.time()

    def get(self, url: str, *, params=None, allow_cache=True, reintentos=2):
        clave = url if params is None else f"{url}|{sorted(params.items())}"
        if allow_cache and clave in self._cache:
            return self._cache[clave]

        if not self.permitido(url):
            self._cache[clave] = None
            return None

        resp = None
        for intento in range(reintentos + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429:
                    time.sleep(2 + intento * 3)
                    continue
                break
            except requests.RequestException:
                if intento == reintentos:
                    resp = None
                else:
                    time.sleep(1 + intento)
        if allow_cache:
            self._cache[clave] = resp
        return resp

    def get_json(self, url: str, *, params=None):
        r = self.get(url, params=params)
        if r is None or r.status_code != 200:
            return None
        ctype = r.headers.get("content-type", "")
        if "json" not in ctype and not r.text.lstrip().startswith(("{", "[")):
            return None
        try:
            return r.json()
        except ValueError:
            return None


# -- utilidades de texto ------------------------------------------------

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def limpiar_html(texto) -> str:
    if not texto:
        return ""
    if not isinstance(texto, str):
        texto = str(texto)
    texto = re.sub(r"<br\s*/?>", " | ", texto, flags=re.I)
    texto = re.sub(r"</(p|li|tr|div|h\d)>", " | ", texto, flags=re.I)
    texto = _TAGS.sub(" ", texto)
    texto = html_lib.unescape(texto).replace("\xa0", " ")
    texto = _WS.sub(" ", texto).strip(" |").strip()
    return re.sub(r"(\s*\|\s*)+", " | ", texto)


def recortar(texto: str, limite: int = 900) -> str:
    texto = texto or ""
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def normalizar_precio(valor) -> str:
    """Devuelve el precio como número plano en texto: '1234.50'."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, (int, float)):
        return f"{float(valor):.2f}"
    s = str(valor).strip()
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s:
        return ""
    # Decide cuál es el separador decimal.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # "1,50" -> decimal ; "1,500" -> miles
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    try:
        return f"{float(s):.2f}"
    except ValueError:
        return ""


def base_url(url: str) -> str:
    p = urlparse(url if "//" in url else "https://" + url)
    scheme = p.scheme or "https"
    return f"{scheme}://{p.netloc}"


def normalizar_url_entrada(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url.rstrip("/")
