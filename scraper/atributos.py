"""Extrae atributos técnicos del texto del producto: medidas, peso, capacidad,
color, material y garantía. Todo se normaliza a centímetros y kilogramos."""

from __future__ import annotations

import re

from .filtro import formas, sin_acentos, tokens

_ESPACIOS = re.compile(r"\s+")


def _tecnico(texto: str) -> str:
    """Minúsculas y sin acentos, pero conservando puntuación: hace falta para
    leer '80.5 cm', '80 x 45 cm' o '32"'."""
    return _ESPACIOS.sub(" ", sin_acentos((texto or "").lower()))

NUM = r"(\d{1,5}(?:[.,]\d{1,3})?)"

A_CM = {"cm": 1.0, "centimetro": 1.0, "centimetros": 1.0, "mm": 0.1, "milimetro": 0.1, "milimetros": 0.1,
        "m": 100.0, "metro": 100.0, "metros": 100.0, "in": 2.54, "pulg": 2.54, "pulgada": 2.54,
        "pulgadas": 2.54, '"': 2.54, "''": 2.54, "ft": 30.48, "pie": 30.48, "pies": 30.48}

A_KG = {"kg": 1.0, "kgs": 1.0, "kilo": 1.0, "kilos": 1.0, "kilogramo": 1.0, "kilogramos": 1.0,
        "g": 0.001, "gr": 0.001, "grs": 0.001, "gramo": 0.001, "gramos": 0.001,
        "lb": 0.45359, "lbs": 0.45359, "libra": 0.45359, "libras": 0.45359,
        "oz": 0.02835, "onza": 0.02835, "onzas": 0.02835, "ton": 1000.0}

A_L = {"l": 1.0, "lt": 1.0, "lts": 1.0, "litro": 1.0, "litros": 1.0,
       "ml": 0.001, "mililitro": 0.001, "mililitros": 0.001, "cc": 0.001,
       "gal": 3.785, "galon": 3.785, "galones": 3.785}

UNID_LARGO = r"(cm|mm|m|in|pulg(?:adas?)?|ft|pies?|centimetros?|milimetros?|metros?|\"|'')"
UNID_PESO = r"(kg|kgs|kilos?|kilogramos?|g|gr|grs|gramos?|lb|lbs|libras?|oz|onzas?|ton)"
UNID_VOL = r"(ml|l|lt|lts|litros?|mililitros?|cc|gal|galones?)"

# --- medidas sueltas: "alto: 80 cm", "altura 80cm", "80 cm de alto"
_ETIQUETAS = {
    "alto_cm": r"alt(?:o|ura)|height",
    "ancho_cm": r"anch(?:o|ura)|width",
    "largo_cm": r"larg(?:o|ura)|longitud|length",
    "profundidad_cm": r"profundidad|fondo|depth",
    "diametro_cm": r"diametro|diameter",
}

_ANTES = {k: re.compile(rf"(?:{v})\s*(?:aprox\.?|de|:|=)?\s*{NUM}\s*{UNID_LARGO}", re.I) for k, v in _ETIQUETAS.items()}
_DESPUES = {k: re.compile(rf"{NUM}\s*{UNID_LARGO}\s*(?:de\s+)?(?:{v})\b", re.I) for k, v in _ETIQUETAS.items()}

# --- medidas combinadas: "80 x 45 x 90 cm"
_COMBO = re.compile(rf"{NUM}\s*[x×*]\s*{NUM}(?:\s*[x×*]\s*{NUM})?\s*{UNID_LARGO}", re.I)
_COMBO_ETIQUETADO = re.compile(
    rf"(?:medidas?|dimensiones?|tama[nñ]o|size)\s*(?:aprox\.?)?\s*[:=]?\s*"
    rf"({NUM}\s*[x×*]\s*{NUM}(?:\s*[x×*]\s*{NUM})?\s*{UNID_LARGO}?)",
    re.I,
)

_PESO = re.compile(rf"(?:peso|weight|pesa)\s*(?:aprox\.?|neto|bruto|de|:|=)?\s*{NUM}\s*{UNID_PESO}\b", re.I)
_PESO_SUELTO = re.compile(rf"\b{NUM}\s*{UNID_PESO}\b(?!\s*(?:de\s+)?(?:capacidad|carga))", re.I)
_VOLUMEN = re.compile(rf"\b{NUM}\s*{UNID_VOL}\b", re.I)
_GARANTIA = re.compile(
    r"garantia\s*(?:de|por|:)?\s*(\d{1,2})\s*(anos?|meses?)|(\d{1,2})\s*(anos?|meses?)\s*de\s*garantia", re.I
)

COLORES = [
    "blanco", "negro", "gris", "plata", "dorado", "oro", "beige", "crema", "marfil", "hueso", "arena",
    "cafe", "chocolate", "camel", "miel", "nogal", "roble", "cedro", "caoba", "natural",
    "rojo", "vino", "borgona", "rosa", "coral", "naranja", "terracota", "amarillo", "mostaza",
    "verde", "olivo", "menta", "turquesa", "aqua", "azul", "marino", "celeste", "morado",
    "lila", "violeta", "purpura", "transparente", "multicolor",
]

MATERIALES = [
    "madera", "roble", "pino", "nogal", "cedro", "mdf", "aglomerado", "bambu", "ratan", "mimbre",
    "metal", "acero", "aluminio", "hierro", "laton", "bronce", "cobre",
    "vidrio", "cristal", "ceramica", "porcelana", "marmol", "granito", "piedra", "concreto",
    "plastico", "policarbonato", "acrilico", "resina", "silicon",
    "piel", "cuero", "gamuza", "terciopelo", "lino", "algodon", "poliester", "nylon", "lona",
    "yute", "corcho", "papel", "carton", "melamina",
]


def _num(txt: str) -> float | None:
    if not txt:
        return None
    t = txt.replace(",", ".") if txt.count(",") == 1 and len(txt.split(",")[-1]) <= 2 else txt.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _fmt(valor: float | None) -> str:
    if valor is None:
        return ""
    return f"{valor:.2f}".rstrip("0").rstrip(".")


def _a_cm(valor: str, unidad: str) -> str:
    n = _num(valor)
    factor = A_CM.get((unidad or "cm").lower().strip())
    return _fmt(n * factor) if n is not None and factor else ""


def _a_kg(valor: str, unidad: str) -> str:
    n = _num(valor)
    factor = A_KG.get((unidad or "kg").lower().strip())
    if n is None or not factor:
        return ""
    kg = n * factor
    return f"{kg:.3f}".rstrip("0").rstrip(".") if kg < 1 else _fmt(kg)


def _capacidad(texto: str) -> str:
    m = _VOLUMEN.search(texto)
    if not m:
        return ""
    n, unidad = _num(m.group(1)), m.group(2).lower()
    factor = A_L.get(unidad)
    if n is None or not factor:
        return ""
    litros = n * factor
    return f"{_fmt(litros)} L" if litros >= 1 else f"{_fmt(litros * 1000)} ml"


def _medidas(texto: str) -> dict:
    salida = {k: "" for k in _ETIQUETAS}
    dimensiones = ""

    for clave in _ETIQUETAS:
        for rx in (_ANTES[clave], _DESPUES[clave]):
            m = rx.search(texto)
            if m:
                salida[clave] = _a_cm(m.group(1), m.group(2))
                if salida[clave]:
                    break

    m = _COMBO_ETIQUETADO.search(texto) or _COMBO.search(texto)
    if m:
        crudo = m.group(0)
        combo = _COMBO.search(crudo) or _COMBO.search(texto)
        if combo:
            unidad = combo.group(4) or "cm"
            partes = [combo.group(1), combo.group(2), combo.group(3)]
            partes = [_a_cm(p, unidad) for p in partes if p]
            dimensiones = (" x ".join(partes) + " cm") if partes else ""
            # Convención habitual: largo x ancho x alto.
            orden = ["largo_cm", "ancho_cm", "alto_cm"] if len(partes) == 3 else ["ancho_cm", "alto_cm"]
            for clave, valor in zip(orden, partes):
                if not salida[clave]:
                    salida[clave] = valor

    salida["dimensiones"] = dimensiones
    return salida


def _lista(texto: str, vocabulario: list[str], limite: int = 3) -> str:
    """Busca palabras del vocabulario tolerando plurales y género."""
    toks = tokens(texto)
    hallados = [p for p in vocabulario if formas(p) & toks]
    return ", ".join(hallados[:limite])


def _de_etiqueta(texto: str, etiqueta: str) -> str:
    m = re.search(rf"{etiqueta}\s*[:=]\s*([^|;\n]{{2,40}})", texto, re.I)
    return m.group(1).strip(" .,") if m else ""


def enriquecer(producto, texto_extra: str = "") -> None:
    """Rellena los campos técnicos que sigan vacíos, sin pisar lo ya extraído."""
    crudo = " | ".join(
        x for x in [producto.nombre, producto.variante, producto.caracteristicas, producto.descripcion, texto_extra] if x
    )
    texto = _tecnico(crudo)

    medidas = _medidas(texto)
    for clave, valor in medidas.items():
        if valor and not getattr(producto, clave, ""):
            setattr(producto, clave, valor)

    if not producto.peso_kg:
        m = _PESO.search(texto) or _PESO_SUELTO.search(texto)
        if m:
            producto.peso_kg = _a_kg(m.group(1), m.group(2))

    if not producto.capacidad:
        producto.capacidad = _capacidad(texto)

    if not producto.color:
        producto.color = _de_etiqueta(crudo, "color") or _lista(crudo, COLORES, 2)

    if not producto.material:
        producto.material = _de_etiqueta(crudo, "material") or _lista(crudo, MATERIALES, 3)

    if not producto.garantia:
        m = _GARANTIA.search(texto)
        if m:
            cantidad = m.group(1) or m.group(3)
            unidad = m.group(2) or m.group(4)
            unidad = {"ano": "año", "anos": "años"}.get(unidad.lower(), unidad.lower())
            producto.garantia = f"{cantidad} {unidad}"

    calcular_descuento(producto)


def calcular_descuento(producto) -> None:
    try:
        precio = float(producto.precio)
        lista = float(producto.precio_lista)
    except (TypeError, ValueError):
        return
    if lista > precio > 0:
        producto.descuento_pct = f"{round((lista - precio) / lista * 100)}"
