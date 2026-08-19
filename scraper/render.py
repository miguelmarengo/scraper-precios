"""Renderizado opcional con un navegador real (Playwright + Chromium), gratis y
de código abierto, para catálogos que se arman con JavaScript (React, Vue,
Angular, etc.) y por eso un requests.get() normal solo ve una página vacía.

Importante — qué SÍ hace y qué NO hace, para que quede claro su límite:
  • SÍ: abre la página con un navegador de verdad y deja que corra su propio
    JavaScript, exactamente como le pasaría a cualquier persona que la visita.
    Eso es todo lo que hace un buscador como Google cuando indexa un sitio.
  • NO: no evade el robots.txt (sigue pasando por el mismo chequeo de
    `Fetcher.permitido`), no inicia sesión en tu lugar si el sitio exige
    login, y no resuelve CAPTCHAs ni burla sistemas anti-bot (Cloudflare,
    Akamai, etc.). Esos son controles de acceso deliberados del sitio, y esta
    herramienta no está pensada para saltárselos.
"""

from __future__ import annotations

import re

from .core import USER_AGENT

try:
    from playwright.sync_api import sync_playwright
    _DISPONIBLE = True
except Exception:  # Playwright no instalado, o falta `playwright install chromium`.
    _DISPONIBLE = False

_RECURSOS_PESADOS = re.compile(r"\.(?:png|jpe?g|gif|webp|svg|woff2?|ttf|eot|mp4)(?:\?.*)?$", re.I)


def disponible() -> bool:
    """True si se puede intentar renderizar (el paquete está instalado)."""
    return _DISPONIBLE


class ErrorRenderizador(RuntimeError):
    pass


class Renderizador:
    """Envuelve un navegador Chromium que se abre una sola vez por corrida
    (abrir un navegador de verdad no es gratis en tiempo, así que se reutiliza
    para todas las páginas que lo necesiten, no una vez por página)."""

    def __init__(self, timeout_ms: int = 15000):
        if not _DISPONIBLE:
            raise ErrorRenderizador(
                "Playwright no está instalado. En tu terminal corre:\n"
                "  pip install playwright\n"
                "  playwright install chromium\n"
                "(los dos son gratis y de código abierto; el segundo descarga el navegador, ~180 MB)."
            )
        self.timeout_ms = timeout_ms
        self.paginas_renderizadas = 0
        self.fallidas = 0
        self._pw = sync_playwright().start()
        try:
            self._navegador = self._pw.chromium.launch(headless=True)
            self._contexto = self._navegador.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1366, "height": 900},
                locale="es-MX",
            )
            # No cargar imágenes/fuentes/video acelera mucho el renderizado y no
            # afecta a los datos estructurados (JSON-LD, meta tags) que nos interesan.
            self._contexto.route(_RECURSOS_PESADOS, lambda ruta: ruta.abort())
        except Exception as e:
            self._pw.stop()
            raise ErrorRenderizador(
                "No se pudo abrir el navegador. Si es la primera vez, corre "
                "'playwright install chromium' y vuelve a intentar."
            ) from e

    def obtener_html(self, url: str) -> str | None:
        """Abre la URL en una pestaña nueva, deja que su JavaScript corra, y
        devuelve el HTML ya renderizado. None si no se pudo cargar a tiempo."""
        pagina = self._contexto.new_page()
        try:
            pagina.goto(url, timeout=self.timeout_ms, wait_until="networkidle")
            html = pagina.content()
            self.paginas_renderizadas += 1
            return html
        except Exception:
            self.fallidas += 1
            return None
        finally:
            pagina.close()

    def cerrar(self) -> None:
        try:
            self._contexto.close()
            self._navegador.close()
            self._pw.stop()
        except Exception:
            pass
