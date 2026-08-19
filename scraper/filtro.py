"""Filtro de productos escrito en lenguaje natural sencillo.

Ejemplos que entiende:

    sillones blancos          -> deben aparecer las dos palabras
    verduras verdes           -> plurales y género se resuelven solos
    sillon | sofa | loveseat  -> cualquiera de las tres
    "sofá cama"               -> frase exacta entre comillas
    sillones -piel            -> sillones, pero excluyendo los de piel
    blancos | negros -oferta  -> se combinan

Todo se compara sin acentos, sin mayúsculas y sin distinguir singular/plural
ni masculino/femenino.
"""

from __future__ import annotations

import re
import unicodedata

_NO_ALFA = re.compile(r"[^0-9a-záéíóúüñ]+", re.I)


def sin_acentos(texto: str) -> str:
    desc = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in desc if unicodedata.category(c) != "Mn")


def normalizar(texto: str) -> str:
    """minúsculas, sin acentos, sin puntuación."""
    texto = sin_acentos((texto or "").lower())
    return _NO_ALFA.sub(" ", texto).strip()


def formas(palabra: str) -> set[str]:
    """Todas las formas plausibles de una palabra: la original, sus posibles
    singulares y su variante de género.

    Se generan varias a propósito porque en español el plural es ambiguo sin
    diccionario: «verdes» puede venir de *verde* (+s) o de *verd* (+es), y
    «sillones» de *sillon* (+es). Al comparar conjuntos, basta con que
    coincida una forma, así que ambas interpretaciones conviven sin problema.
    """
    p = palabra
    salida = {p}
    if len(p) > 3:
        if p.endswith("ces"):                                   # luces -> luz
            salida.add(p[:-3] + "z")
        if p.endswith("es") and len(p) > 4 and p[-3] in "nrldjszxt":  # sillones -> sillon
            salida.add(p[:-2])
        if p.endswith("s") and not p.endswith("ss"):            # blancos -> blanco
            salida.add(p[:-1])
    for base in list(salida):                                   # blanco <-> blanca
        if len(base) >= 5:
            if base.endswith("o"):
                salida.add(base[:-1] + "a")
            elif base.endswith("a"):
                salida.add(base[:-1] + "o")
    return salida


def singular(palabra: str) -> str:
    """La forma singular más corta que se puede deducir. Solo informativa."""
    return min(formas(palabra), key=len)


def tokens(texto: str) -> set[str]:
    salida: set[str] = set()
    for t in normalizar(texto).split():
        salida |= formas(t)
    return salida


# ------------------------------------------------------------------ parseo

_ENTRECOMILLADO = re.compile(r'(-?)"([^"]+)"')


def _parsear(consulta: str) -> tuple[list[list[str]], list[str]]:
    """Devuelve (grupos_OR, exclusiones). Cada grupo es una lista de términos AND."""
    consulta = consulta or ""
    exclusiones: list[str] = []
    frases: dict[str, str] = {}

    # Aparta las frases entre comillas para que no se rompan al separar por espacios.
    def _guardar(m):
        marca = f"\x00{len(frases)}\x00"
        if m.group(1) == "-":
            exclusiones.append(m.group(2))
            return " "
        frases[marca] = m.group(2)
        return " " + marca + " "

    consulta = _ENTRECOMILLADO.sub(_guardar, consulta)

    restante = []
    for pieza in consulta.split():
        if pieza.startswith("-") and len(pieza) > 1:
            exclusiones.append(pieza[1:])
        else:
            restante.append(pieza)

    grupos: list[list[str]] = []
    actual: list[str] = []
    for pieza in restante:
        if pieza == "|":
            grupos.append(actual)
            actual = []
            continue
        if "|" in pieza:
            partes = pieza.split("|")
            for i, sub in enumerate(partes):
                if sub:
                    actual.append(frases.get(sub, sub))
                if i < len(partes) - 1:
                    grupos.append(actual)
                    actual = []
            continue
        actual.append(frases.get(pieza, pieza))
    grupos.append(actual)

    grupos = [g for g in grupos if g]
    return grupos, exclusiones


def _coincide_termino(termino: str, texto_norm: str, tokens_texto: set[str]) -> bool:
    termino_norm = normalizar(termino)
    if not termino_norm:
        return True
    if " " in termino_norm:                     # frase: subcadena
        return termino_norm in texto_norm
    return bool(formas(termino_norm) & tokens_texto)


class Filtro:
    def __init__(
        self,
        consulta: str = "",
        *,
        precio_min: float | None = None,
        precio_max: float | None = None,
        solo_disponibles: bool = False,
    ):
        self.consulta = (consulta or "").strip()
        self.grupos, self.exclusiones = _parsear(self.consulta)
        self.precio_min = precio_min
        self.precio_max = precio_max
        self.solo_disponibles = solo_disponibles

    # ------------------------------------------------------------ estado
    @property
    def hay_texto(self) -> bool:
        return bool(self.grupos or self.exclusiones)

    @property
    def activo(self) -> bool:
        return self.hay_texto or self.precio_min is not None or self.precio_max is not None or self.solo_disponibles

    @property
    def terminos_sueltos(self) -> list[str]:
        """Todos los términos positivos, útil para pre-filtrar URLs."""
        salida = []
        for g in self.grupos:
            for t in g:
                salida.extend(normalizar(t).split())
        return [t for t in salida if len(t) >= 3]

    # ------------------------------------------------------------ pruebas
    def texto_coincide(self, texto: str) -> bool:
        if not self.hay_texto:
            return True
        texto_norm = normalizar(texto)
        toks = tokens(texto)
        for termino in self.exclusiones:
            if _coincide_termino(termino, texto_norm, toks):
                return False
        if not self.grupos:
            return True
        return any(
            all(_coincide_termino(t, texto_norm, toks) for t in grupo)
            for grupo in self.grupos
        )

    def texto_coincide_parcial(self, texto: str) -> bool:
        """Cierto si aparece AL MENOS un término. Se usa solo para descartar
        URLs obviamente ajenas antes de descargarlas."""
        if not self.terminos_sueltos:
            return True
        toks = tokens(texto)
        texto_norm = normalizar(texto)
        for termino in self.exclusiones:
            if _coincide_termino(termino, texto_norm, toks):
                return False
        return any(_coincide_termino(t, texto_norm, toks) for t in self.terminos_sueltos)

    def coincide(self, producto) -> bool:
        if self.solo_disponibles and producto.disponible == "No":
            return False
        if self.precio_min is not None or self.precio_max is not None:
            try:
                precio = float(producto.precio)
            except (TypeError, ValueError):
                return False
            if self.precio_min is not None and precio < self.precio_min:
                return False
            if self.precio_max is not None and precio > self.precio_max:
                return False
        return self.texto_coincide(producto.texto_busqueda())

    def aplicar(self, productos: list) -> list:
        if not self.activo:
            return productos
        return [p for p in productos if self.coincide(p)]
