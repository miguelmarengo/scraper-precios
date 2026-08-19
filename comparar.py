"""Compara el mismo producto en varias tiendas, agregando una columna de
precio (y disponibilidad) por cada tienda a un solo "tablero de comparación".

El emparejamiento no puede depender del SKU ni de la liga: cada tienda usa
los suyos propios. Se hace por el nombre del producto (y su variante),
normalizado con las mismas reglas que el buscador de la app (ver
scraper.filtro): sin acentos, sin mayúsculas, tolerando plural y género.

    ✅ nombre idéntico (normalizado)       -> se empareja solo, sin preguntar
    🤔 nombre parecido, no idéntico        -> se enseña para que tú decidas
    🆕 no se parece a nada de lo que había -> renglón nuevo

Nunca se borra una columna de otra tienda ni un renglón que ya estaba. Cada
corrida solo puede *agregar* una columna nueva (la de su tienda) y rellenar
renglones; nunca quita lo que dejaron corridas anteriores.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scraper import COLUMNS
from scraper.filtro import normalizar, tokens

COL_IMAGEN = "foto"
COL_PRODUCTO = "producto"
COL_VARIANTE = "variante"
COL_CATEGORIA = "categoria"
COL_DECISION = "decisión"
COL_MEJOR = "🏆 mejor precio"
META = [COL_IMAGEN, COL_PRODUCTO, COL_VARIANTE, COL_CATEGORIA, COL_DECISION, COL_MEJOR]

# Opciones del menú desplegable de la columna `decisión` (se valida en Sheets).
OPCIONES_DECISION = ["👀 viendo", "⭐ favorito", "🛒 comprado"]

SEPARADOR = " · "

# Por debajo de esto, dos nombres se consideran productos distintos y ni
# siquiera se sugiere la coincidencia.
UMBRAL_PARECIDO = 0.5


def columnas_tienda(tienda: str) -> tuple[str, str, str, str]:
    """Nombres de columna que le corresponden a una tienda: precio, si está
    disponible, la liga directa al producto, y cuándo se revisó por última
    vez ahí."""
    return (
        f"precio{SEPARADOR}{tienda}",
        f"disponible{SEPARADOR}{tienda}",
        f"liga{SEPARADOR}{tienda}",
        f"actualizado{SEPARADOR}{tienda}",
    )


def tienda_de_columna(columna: str) -> str | None:
    """El nombre de tienda escondido en una columna 'precio · Liverpool', o
    None si la columna no es de ninguna tienda."""
    if SEPARADOR not in columna:
        return None
    prefijo, tienda = columna.split(SEPARADOR, 1)
    if prefijo in ("precio", "disponible", "liga", "actualizado"):
        return tienda
    return None


def _tiendas_de_encabezado(encabezado: list[str]) -> list[str]:
    """Todas las tiendas que ya tienen columna de precio en este tablero,
    en el orden en que aparecen."""
    tiendas: list[str] = []
    for h in encabezado:
        if h.startswith(f"precio{SEPARADOR}"):
            t = tienda_de_columna(h)
            if t and t not in tiendas:
                tiendas.append(t)
    return tiendas


def _mejor_precio(fila: dict, tiendas: list[str]) -> str:
    """Texto tipo '$899.00 · Liverpool' con la tienda más barata para este
    producto entre las que ya se han revisado. Vacío si ninguna tienda
    reportó un precio numérico."""
    mejor_tienda, mejor_valor = None, None
    for t in tiendas:
        precio_c, *_resto = columnas_tienda(t)
        try:
            valor = float(fila.get(precio_c, ""))
        except (TypeError, ValueError):
            continue
        if mejor_valor is None or valor < mejor_valor:
            mejor_valor, mejor_tienda = valor, t
    if mejor_tienda is None:
        return ""
    return f"${mejor_valor:,.2f} · {mejor_tienda}"


def _clave(nombre: str, variante: str) -> str:
    return f"{normalizar(nombre)}|{normalizar(variante)}"


def _similitud(nombre_a: str, variante_a: str, nombre_b: str, variante_b: str) -> float:
    ta = tokens(nombre_a) | tokens(variante_a)
    tb = tokens(nombre_b) | tokens(variante_b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class Candidato:
    """Un producto recién extraído que se parece a un renglón que ya
    existía, pero no lo suficiente como para emparejarlo sin preguntar."""

    indice_producto: int
    indice_existente: int
    similitud: float
    nombre_nuevo: str
    variante_nuevo: str
    nombre_existente: str
    variante_existente: str


@dataclass
class PlanComparacion:
    tienda: str
    encabezado: list[str]
    filas_existentes: list[dict]
    productos_pendientes: list[dict]   # sin emparejamiento exacto: nuevos o "parecidos" sin confirmar
    candidatos: list[Candidato]
    resumen: dict = field(default_factory=dict)

    def tabla(self, confirmados: dict[int, bool] | None = None) -> tuple[list[list], dict]:
        """confirmados: {indice_producto: True} para los `candidatos` que el
        usuario marcó como "sí, es el mismo producto". Todo lo demás se
        agrega como renglón nuevo.

        Devuelve (tabla_lista_para_escribir, resumen_de_esta_corrida).
        """
        confirmados = confirmados or {}
        precio_c, disp_c, liga_c, act_c = columnas_tienda(self.tienda)
        candidatos_por_producto = {c.indice_producto: c for c in self.candidatos}

        filas = [dict(f) for f in self.filas_existentes]
        nuevas: list[dict] = []
        actualizadas = 0

        for i, prod in enumerate(self.productos_pendientes):
            candidato = candidatos_por_producto.get(i)
            if candidato is not None and confirmados.get(i):
                fila = filas[candidato.indice_existente]
                actualizadas += 1
            else:
                fila = {
                    COL_IMAGEN: prod.get("foto", ""),
                    COL_PRODUCTO: prod.get("nombre", ""),
                    COL_VARIANTE: prod.get("variante", ""),
                    COL_CATEGORIA: prod.get("categoria", ""),
                }
                nuevas.append(fila)
            fila[precio_c] = prod.get("precio", "")
            fila[disp_c] = prod.get("disponible", "")
            fila[liga_c] = prod.get("url_producto", "")
            fila[act_c] = prod.get("fecha_extraccion", "")

        todas = filas + nuevas
        tiendas = _tiendas_de_encabezado(self.encabezado)
        for fila in todas:
            fila[COL_MEJOR] = _mejor_precio(fila, tiendas)

        cuerpo = [[f.get(c, "") for c in self.encabezado] for f in todas]
        resumen = {
            **self.resumen,
            "nuevos_finales": len(nuevas),
            "actualizados_finales": self.resumen.get("exactos", 0) + actualizadas,
            "total_final": len(todas),
        }
        return [self.encabezado] + cuerpo, resumen


def construir_comparacion(
    encabezado_previo: list[str],
    filas_previas: list[list],
    productos: list,
    tienda: str,
) -> PlanComparacion:
    """Compara lo que ya había en el tablero contra lo recién extraído de
    `tienda`, sin tocar la hoja ni la base de datos: solo devuelve el plan
    para poder enseñárselo al usuario antes de aplicarlo."""
    tienda = (tienda or "Tienda").strip() or "Tienda"
    encabezado_previo = [str(h).strip() for h in (encabezado_previo or [])]
    precio_c, disp_c, liga_c, act_c = columnas_tienda(tienda)

    # Orden final del encabezado: META, luego cada tienda en el orden en que
    # apareció (la actual al final si es nueva), luego cualquier columna
    # propia que el usuario haya escrito a mano.
    tiendas_previas: list[str] = []
    for h in encabezado_previo:
        t = tienda_de_columna(h)
        if t and t not in tiendas_previas:
            tiendas_previas.append(t)
    if tienda not in tiendas_previas:
        tiendas_previas.append(tienda)

    encabezado = list(META)
    for t in tiendas_previas:
        encabezado.extend(columnas_tienda(t))
    conocidas = set(encabezado)
    propias = [h for h in encabezado_previo if h and h not in conocidas]
    encabezado += propias

    indice_previo = {h: i for i, h in enumerate(encabezado_previo) if h}

    def como_dict(fila: list) -> dict:
        return {h: (fila[i] if i < len(fila) else "") for h, i in indice_previo.items()}

    filas_existentes = [como_dict(f) for f in (filas_previas or [])]
    filas_existentes = [d for d in filas_existentes if any(str(v).strip() for v in d.values())]

    indice_por_clave: dict[str, int] = {}
    for i, d in enumerate(filas_existentes):
        k = _clave(d.get(COL_PRODUCTO, ""), d.get(COL_VARIANTE, ""))
        if k and k not in indice_por_clave:
            indice_por_clave[k] = i

    productos_dict: list[dict] = []
    for p in productos:
        d = {c: getattr(p, c, "") for c in COLUMNS}
        d["foto"] = p.foto
        productos_dict.append(d)

    exactos = 0
    duplicados = 0
    candidatos: list[Candidato] = []
    pendientes: list[dict] = []
    vistos: set[str] = set()

    for prod in productos_dict:
        k = _clave(prod.get("nombre", ""), prod.get("variante", ""))
        if k and k in vistos:
            duplicados += 1
            continue

        pos = indice_por_clave.get(k) if k else None
        if pos is not None:
            fila = filas_existentes[pos]
            fila[precio_c] = prod.get("precio", "")
            fila[disp_c] = prod.get("disponible", "")
            fila[liga_c] = prod.get("url_producto", "")
            fila[act_c] = prod.get("fecha_extraccion", "")
            exactos += 1
            if k:
                vistos.add(k)
            continue

        if k:
            vistos.add(k)

        mejor_idx, mejor_sim = None, 0.0
        for j, existente in enumerate(filas_existentes):
            sim = _similitud(
                prod.get("nombre", ""), prod.get("variante", ""),
                existente.get(COL_PRODUCTO, ""), existente.get(COL_VARIANTE, ""),
            )
            if sim > mejor_sim:
                mejor_idx, mejor_sim = j, sim

        if mejor_idx is not None and mejor_sim >= UMBRAL_PARECIDO:
            candidatos.append(Candidato(
                indice_producto=len(pendientes),
                indice_existente=mejor_idx,
                similitud=round(mejor_sim, 2),
                nombre_nuevo=prod.get("nombre", ""),
                variante_nuevo=prod.get("variante", ""),
                nombre_existente=filas_existentes[mejor_idx].get(COL_PRODUCTO, ""),
                variante_existente=filas_existentes[mejor_idx].get(COL_VARIANTE, ""),
            ))
        pendientes.append(prod)

    return PlanComparacion(
        tienda=tienda,
        encabezado=encabezado,
        filas_existentes=filas_existentes,
        productos_pendientes=pendientes,
        candidatos=candidatos,
        resumen={
            "tienda": tienda,
            "exactos": exactos,
            "para_revisar": len(candidatos),
            "extraidos": len(productos_dict),
            "duplicados": duplicados,
            "renglones_previos": len(filas_existentes),
            "tiendas": tiendas_previas,
        },
    )
