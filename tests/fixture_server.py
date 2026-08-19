"""Servidor de prueba: simula una tienda Shopify y una tienda genérica con JSON-LD."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# ------------------------------------------------------------------ Shopify

SHOPIFY_PRODUCTS = {
    "products": [
        {
            "id": 1,
            "title": "Taza de cerámica",
            "handle": "taza-ceramica",
            "vendor": "Alfarería Sur",
            "product_type": "Cocina",
            "tags": ["cocina", "regalo"],
            "body_html": "<p>Taza artesanal de 350 ml.</p><ul><li>Apta para microondas</li></ul>",
            "options": [{"name": "Color"}, {"name": "Tamaño"}],
            "images": [{"src": "https://cdn.test/taza.jpg"}],
            "variants": [
                {"id": 11, "title": "Azul / Chico", "option1": "Azul", "option2": "Chico",
                 "sku": "TZ-AZ-CH", "price": "249.00", "compare_at_price": "299.00", "available": True},
                {"id": 12, "title": "Rojo / Grande", "option1": "Rojo", "option2": "Grande",
                 "sku": "TZ-RJ-GR", "price": "319.50", "compare_at_price": None, "available": False},
            ],
        },
        {
            "id": 3,
            "title": "Sillón Oslo",
            "handle": "sillon-oslo",
            "vendor": "Nórdico",
            "product_type": "Sala",
            "tags": ["sala", "tapizado"],
            "body_html": "<p>Sillón tapizado en lino.</p><ul><li>Medidas: 75 x 80 x 90 cm</li>"
                         "<li>Garantía de 2 años</li></ul>",
            "options": [{"name": "Color"}],
            "images": [{"src": "https://cdn.test/sillon-1.jpg"}, {"src": "https://cdn.test/sillon-2.jpg"}],
            "variants": [
                {"id": 31, "title": "Blanco", "option1": "Blanco", "sku": "SO-BL", "price": "12999.00",
                 "compare_at_price": "15999.00", "available": True, "weight": 18000, "weight_unit": "g"},
                {"id": 32, "title": "Negro", "option1": "Negro", "sku": "SO-NE", "price": "12999.00",
                 "compare_at_price": None, "available": True, "weight": 18000, "weight_unit": "g"},
            ],
        },
        {
            "id": 2,
            "title": "Plato hondo",
            "handle": "plato-hondo",
            "vendor": "Alfarería Sur",
            "product_type": "Cocina",
            "tags": "cocina",
            "body_html": "<p>Plato hondo de 22 cm.</p>",
            "options": [{"name": "Title"}],
            "images": [{"src": "https://cdn.test/plato.jpg"}],
            "variants": [
                {"id": 21, "title": "Default Title", "option1": "Default Title",
                 "sku": "PL-22", "price": "189", "compare_at_price": None, "available": True},
            ],
        },
    ]
}

SHOPIFY_JS = {
    "taza-ceramica": {"variants": [
        {"id": 11, "inventory_quantity": 42, "inventory_management": "shopify"},
        {"id": 12, "inventory_quantity": 0, "inventory_management": "shopify"},
    ]},
    "plato-hondo": {"variants": [{"id": 21, "inventory_quantity": 7, "inventory_management": "shopify"}]},
    "sillon-oslo": {"variants": [
        {"id": 31, "inventory_quantity": 3, "inventory_management": "shopify"},
        {"id": 32, "inventory_quantity": 9, "inventory_management": "shopify"},
    ]},
}

SHOPIFY_HOME = """<!doctype html><html><head><script>
var Shopify = Shopify || {}; Shopify.currency = {"active":"MXN","rate":"1.0"};
</script></head><body>Tienda</body></html>"""

SHOPIFY_PDP = """<!doctype html><html><body>
<h1>Producto</h1>
<div class="product__shipping-note">Entrega estimada de 3 a 5 días hábiles en todo el país.</div>
</body></html>"""


# ------------------------------------------------------------------ Genérico

GENERIC_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>http://{host}/producto/silla-nordica</loc></url>
<url><loc>http://{host}/producto/mesa-roble</loc></url>
<url><loc>http://{host}/pages/about</loc></url>
</urlset>"""

GENERIC_PDP = """<!doctype html><html><head>
<title>{nombre} | Muebles Test</title>
<meta property="og:image" content="https://cdn.test/{slug}.jpg">
<script type="application/ld+json">
{ld}
</script>
</head><body>
<div class="shipping-info">Env&iacute;o: recibe tu pedido en {dias} d&iacute;as h&aacute;biles.</div>
<p>Solo quedan {inv} piezas disponibles.</p>
</body></html>"""


def _ld(nombre, sku, precio, disponible):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "name": nombre,
        "sku": sku,
        "brand": {"@type": "Brand", "name": "Muebles Test"},
        "category": "Sala",
        "description": f"{nombre} de fabricación nacional.",
        "material": "Roble",
        "color": "Natural",
        "image": [f"https://cdn.test/{sku}-1.jpg", {"@type": "ImageObject", "url": f"https://cdn.test/{sku}-2.jpg"}],
        "height": {"@type": "QuantitativeValue", "value": 850, "unitCode": "MMT"},
        "width": {"@type": "QuantitativeValue", "value": 46, "unitCode": "CMT"},
        "depth": {"@type": "QuantitativeValue", "value": 50, "unitCode": "CMT"},
        "weight": {"@type": "QuantitativeValue", "value": 6500, "unitCode": "GRM"},
        "additionalProperty": [
            {"@type": "PropertyValue", "name": "Alto", "value": "80 cm"},
            {"@type": "PropertyValue", "name": "Garantía", "value": "2 años"},
        ],
        "offers": {
            "@type": "Offer",
            "price": precio,
            "priceCurrency": "MXN",
            "highPrice": str(round(float(precio) * 1.25, 2)),
            "availability": "https://schema.org/InStock" if disponible else "https://schema.org/OutOfStock",
        },
    }, ensure_ascii=False)


GENERIC_ITEMS = {
    "silla-nordica": ("Silla nórdica", "SN-001", "1899.00", True, 5, 12),
    "mesa-roble": ("Mesa de roble", "MR-002", "8450.50", False, 7, 0),
}


# ------------------------------------------------------------------ WooCommerce

WOO_PRODUCTS = [
    {
        "name": "Café de altura 1 kg",
        "sku": "CAF-1K",
        "permalink": "http://127.0.0.1:PORT/producto/cafe-altura",
        "description": "<p>Grano de Chiapas, tueste medio.</p>",
        "short_description": "<p>Tueste medio, notas de cacao.</p>",
        "prices": {"price": "38900", "regular_price": "45000", "currency_code": "MXN", "currency_minor_unit": 2},
        "is_in_stock": True,
        "low_stock_remaining": 4,
        "categories": [{"name": "Café"}, {"name": "Despensa"}],
        "images": [{"src": "https://cdn.test/cafe.jpg"}],
        "attributes": [{"name": "Molienda", "terms": [{"name": "Grano"}, {"name": "Fina"}]}],
        "variation": [],
    },
    {
        "name": "Prensa francesa",
        "sku": "PF-600",
        "permalink": "http://127.0.0.1:PORT/producto/prensa-francesa",
        "description": "<p>600 ml de vidrio borosilicato.</p>",
        "short_description": "",
        "prices": {"price": "72000", "regular_price": "72000", "currency_code": "MXN", "currency_minor_unit": 2},
        "is_in_stock": False,
        "low_stock_remaining": None,
        "categories": [{"name": "Accesorios"}],
        "images": [],
        "attributes": [],
        "variation": [],
    },
]

WOO_PDP = """<!doctype html><html><body>
<div class="woocommerce-shipping-delivery">Entrega en 2 a 4 d&iacute;as h&aacute;biles.</div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _responder(self, cuerpo, tipo="text/html; charset=utf-8", codigo=200):
        datos = cuerpo.encode("utf-8") if isinstance(cuerpo, str) else cuerpo
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        ruta = urlparse(self.path).path
        host = self.headers.get("Host", "localhost")
        modo = self.server.modo
        self.server.peticiones.append(ruta)

        if ruta == "/robots.txt":
            if modo == "robots_bloqueado":
                # Caso real y común: la portada SÍ se puede leer (por eso el chequeo rápido
                # de la URL de entrada no salta), pero el sitemap y las fichas de producto
                # están prohibidas. Sin el diagnóstico de robots.txt, esto se ve igual que
                # "el catálogo está vacío": corre un segundo y no trae nada, sin explicación.
                return self._responder(
                    "User-agent: *\nDisallow: /sitemap.xml\nDisallow: /producto/\n", "text/plain"
                )
            return self._responder(
                f"User-agent: *\nDisallow: /admin\nSitemap: http://{host}/sitemap.xml\n", "text/plain"
            )

        if modo == "robots_bloqueado":
            if ruta in ("/", "/index.html"):
                return self._responder("<html><body>Portada permitida, pero sin ligas útiles.</body></html>")
            # No debería llegar ninguna petición más allá de la portada (todo lo demás está
            # bloqueado por robots.txt), pero por si acaso: si llega, es una falla del
            # fetcher, no de la tienda.
            return self._responder("<html><body>No debiste llegar aquí.</body></html>")

        if modo == "login_wall":
            # Simula una tienda que redirige todo (incluida la portada) a un login externo
            # antes de mostrar nada — como le pasa a algunas tiendas que comparten cuenta
            # con otra más grande. requests debe agotar sus redirecciones y devolver None.
            self.send_response(302)
            self.send_header("Location", f"http://{host}/login?redir={ruta}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if modo == "woo":
            if ruta in ("/wp-json/wc/store/v1/products", "/wp-json/wc/store/products"):
                pagina = int(dict(p.split("=") for p in urlparse(self.path).query.split("&") if "=" in p).get("page", 1))
                cuerpo = WOO_PRODUCTS if pagina == 1 else []
                texto = json.dumps(cuerpo, ensure_ascii=False).replace("127.0.0.1:PORT", host)
                return self._responder(texto, "application/json")
            if ruta.startswith("/producto/"):
                return self._responder(WOO_PDP)
            if ruta in ("/", "/index.html"):
                return self._responder("<html><body>WooCommerce wp-content/plugins/woocommerce</body></html>")
            return self._responder("no", "text/plain", 404)

        if modo == "shopify":
            if ruta == "/products.json":
                return self._responder(json.dumps(SHOPIFY_PRODUCTS), "application/json")
            if ruta.startswith("/products/") and ruta.endswith(".js"):
                handle = ruta[len("/products/"):-3]
                if handle in SHOPIFY_JS:
                    return self._responder(json.dumps(SHOPIFY_JS[handle]), "application/json")
                return self._responder("{}", "application/json", 404)
            if ruta.startswith("/products/"):
                return self._responder(SHOPIFY_PDP)
            if ruta in ("/", "/index.html"):
                return self._responder(SHOPIFY_HOME)
            return self._responder("no", "text/plain", 404)

        # genérico
        if ruta == "/sitemap.xml":
            return self._responder(GENERIC_SITEMAP.format(host=host), "application/xml")
        if ruta.startswith("/producto/"):
            slug = ruta.split("/")[-1]
            if slug not in GENERIC_ITEMS:
                return self._responder("no", "text/plain", 404)
            nombre, sku, precio, disp, dias, inv = GENERIC_ITEMS[slug]
            return self._responder(
                GENERIC_PDP.format(nombre=nombre, slug=slug, ld=_ld(nombre, sku, precio, disp), dias=dias, inv=inv)
            )
        if ruta in ("/", "/index.html"):
            return self._responder("<html><body><a href='/producto/silla-nordica'>Silla</a></body></html>")
        return self._responder("no", "text/plain", 404)


def arrancar(puerto=0, modo="shopify"):
    srv = ThreadingHTTPServer(("127.0.0.1", puerto), Handler)
    srv.modo = modo
    srv.peticiones = []
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    return srv, f"http://127.0.0.1:{srv.server_port}"
