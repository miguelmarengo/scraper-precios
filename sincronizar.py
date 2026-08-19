"""Sincroniza los productos recién extraídos contra una hoja que ya existe.

La idea: tu hoja manda. Nunca se borran renglones ni columnas tuyas. Lo que hace
esta sincronización es comparar renglón por renglón y marcar cada uno:

    🟢 nuevo           no estaba antes; se agrega al final
    🟡 cambió          ya estaba y algún dato se movió; se actualiza y se anota qué cambió
    🔴 no encontrado   estaba antes pero hoy no apareció en la tienda; se deja intacto
    ⚪ sin cambios     ya estaba y todo sigue igual

El emparejamiento se hace por SKU cuando existe, y si no, por la liga del
producto más la variante.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from scraper import COLUMNS

# --- columnas que agrega la sincronización, siempre al principio de la hoja
COL_ESTADO = "estado"
COL_CAMBIOS = "cambios"
COL_REVISION = "revisado_en"
META = [COL_ESTADO, COL_CAMBIOS, COL_REVISION]

NUEVO = "🟢 nuevo"
CAMBIO = "🟡 cambió"
FALTANTE = "🔴 no encontrado"
IGUAL = "⚪ sin cambios"

# Colores de fondo (suaves, para que el texto siga leyéndose).
COLORES = {
    NUEVO: (0.85, 0.94, 0.85),
    CAMBIO: (1.00, 0.96, 0.78),
    FALTANTE: (0.99, 0.86, 0.86),
    IGUAL: (1.00, 1.00, 1.00),
}

# Campos cuyo cambio se reporta. El resto se actualiza en silencio.
VIGILADOS = [
    "precio",
    "precio_lista",
    "descuento_pct",
    "disponible",
    "inventario",
    "tiempo_entrega",
]

ESTRATEGIAS = {
    "auto": "SKU si existe; si no, la liga del producto",
    "sku": "Solo el SKU",
    "url": "La liga del producto (y la variante)",
}


# --------------------------------------------------------------- utilidades

def _limpiar_url(u: str) -> str:
    u = (u or "").strip().lower()
    u = re.sub(r"[?#].*$", "", u)
    return u.rstrip("/")


def clave(fila: dict, estrategia: str = "auto") -> str:
    """Identificador estable de un renglón. Cadena vacía = no se puede emparejar."""
    sku = (fila.get("sku") or "").strip().upper()
    url = _limpiar_url(fila.get("url_producto", ""))
    variante = (fila.get("variante") or "").strip().lower()

    if estrategia == "sku":
        return f"sku:{sku}" if sku else ""
    if estrategia == "url":
        return f"url:{url}|{variante}" if url else ""
    if sku:
        return f"sku:{sku}"
    if url:
        return f"url:{url}|{variante}"
    return ""


def _comparables(a: str, b: str) -> bool:
    """Compara dos celdas tolerando '1299' vs '1299.00' y espacios de más."""
    a, b = (a or "").strip(), (b or "").strip()
    if a == b:
        return True
    try:
        return abs(float(a.replace(",", "")) - float(b.replace(",", ""))) < 0.005
    except ValueError:
        return a.casefold() == b.casefold()


def _describir(campo: str, antes: str, ahora: str) -> str:
    antes = antes or "(vacío)"
    ahora = ahora or "(vacío)"
    return f"{campo}: {antes} → {ahora}"


# --------------------------------------------------------------- el plan

@dataclass
class Plan:
    encabezado: list[str] = field(default_factory=list)
    filas: list[list] = field(default_factory=list)
    estados: list[str] = field(default_factory=list)
    resumen: dict = field(default_factory=dict)
    aviso: str = ""

    @property
    def tabla(self) -> list[list]:
        return [self.encabezado] + self.filas


def construir_plan(
    encabezado_previo: list[str],
    filas_previas: list[list],
    productos: list,
    *,
    estrategia: str = "auto",
    vigilados: list[str] | None = None,
    ahora: str | None = None,
) -> Plan:
    """Compara lo que ya hay en la hoja contra lo recién extraído.

    No toca la base de datos ni la hoja: solo devuelve el plan de escritura,
    para poder enseñárselo al usuario antes de aplicarlo.
    """
    vigilados = vigilados or VIGILADOS
    ahora = ahora or datetime.now().strftime("%Y-%m-%d %H:%M")

    encabezado_previo = [str(h).strip() for h in (encabezado_previo or [])]
    propias = [h for h in encabezado_previo if h and h not in META and h not in COLUMNS]
    # Orden final: marcas de la sincronización, luego nuestras columnas, luego las tuyas.
    encabezado = META + COLUMNS + propias

    indice_previo = {h: i for i, h in enumerate(encabezado_previo) if h}

    def como_dict(fila: list) -> dict:
        return {h: (fila[i] if i < len(fila) else "") for h, i in indice_previo.items()}

    previos = [como_dict(f) for f in (filas_previas or [])]
    previos = [d for d in previos if any(str(v).strip() for v in d.values())]

    # Índice de lo que ya estaba. Si hay claves repetidas, gana la primera.
    por_clave: dict[str, int] = {}
    repetidas = 0
    for i, d in enumerate(previos):
        k = clave(d, estrategia)
        if not k:
            continue
        if k in por_clave:
            repetidas += 1
            continue
        por_clave[k] = i

    # Lo recién extraído, también indexado.
    nuevos: list[dict] = []
    for p in productos:
        d = {c: getattr(p, c, "") for c in COLUMNS}
        d["foto"] = p.foto
        nuevos.append(d)

    emparejados: dict[int, dict] = {}
    sin_emparejar: list[dict] = []
    duplicados_entrantes = 0
    vistos: set[str] = set()

    for d in nuevos:
        k = clave(d, estrategia)
        if k and k in vistos:
            duplicados_entrantes += 1
            continue
        if k:
            vistos.add(k)
        pos = por_clave.get(k) if k else None
        if pos is None or pos in emparejados:
            sin_emparejar.append(d)
        else:
            emparejados[pos] = d

    filas: list[list] = []
    estados: list[str] = []
    conteo = {NUEVO: 0, CAMBIO: 0, FALTANTE: 0, IGUAL: 0}

    def escribir(datos: dict, estado: str, cambios: str, revision: str):
        datos = dict(datos)
        datos[COL_ESTADO] = estado
        datos[COL_CAMBIOS] = cambios
        datos[COL_REVISION] = revision
        filas.append([datos.get(c, "") for c in encabezado])
        estados.append(estado)
        conteo[estado] += 1

    # 1) Los renglones que ya estaban, en su orden original.
    for i, antiguo in enumerate(previos):
        entrante = emparejados.get(i)
        if entrante is None:
            escribir(antiguo, FALTANTE, "", antiguo.get(COL_REVISION, ""))
            continue

        cambios = [
            _describir(campo, antiguo.get(campo, ""), entrante.get(campo, ""))
            for campo in vigilados
            if not _comparables(antiguo.get(campo, ""), entrante.get(campo, ""))
        ]
        fusionado = dict(antiguo)
        fusionado.update(entrante)          # nuestros datos se refrescan
        escribir(fusionado, CAMBIO if cambios else IGUAL, "; ".join(cambios), ahora)

    # 2) Los que no estaban, al final.
    for d in sin_emparejar:
        escribir(d, NUEVO, "", ahora)

    avisos = []
    if repetidas:
        avisos.append(f"{repetidas} renglón(es) de tu hoja comparten identificador; se usó el primero.")
    if duplicados_entrantes:
        avisos.append(f"{duplicados_entrantes} producto(s) extraído(s) estaban repetidos y se omitieron.")
    sin_clave = sum(1 for d in previos if not clave(d, estrategia))
    if sin_clave:
        avisos.append(
            f"{sin_clave} renglón(es) de tu hoja no tienen SKU ni liga, así que no se pueden "
            "emparejar y siempre saldrán en rojo."
        )

    return Plan(
        encabezado=encabezado,
        filas=filas,
        estados=estados,
        resumen={
            "nuevos": conteo[NUEVO],
            "cambiados": conteo[CAMBIO],
            "faltantes": conteo[FALTANTE],
            "iguales": conteo[IGUAL],
            "total": len(filas),
            "previos": len(previos),
            "extraidos": len(nuevos),
            "columnas_propias": propias,
        },
        aviso=" ".join(avisos),
    )


# --------------------------------------------------------------- colores

def agrupar_colores(estados: list[str]) -> list[tuple[int, int, str]]:
    """Junta renglones consecutivos del mismo color en un solo rango,
    para no mandar cientos de peticiones a Google."""
    rangos: list[tuple[int, int, str]] = []
    for i, estado in enumerate(estados):
        if rangos and rangos[-1][2] == estado and rangos[-1][1] == i:
            inicio, _, e = rangos[-1]
            rangos[-1] = (inicio, i + 1, e)
        else:
            rangos.append((i, i + 1, estado))
    return rangos


def peticiones_de_color(sheet_id: int, estados: list[str]) -> list[dict]:
    peticiones = []
    for inicio, fin, estado in agrupar_colores(estados):
        r, g, b = COLORES.get(estado, (1.0, 1.0, 1.0))
        peticiones.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": inicio + 1,   # +1 por el encabezado
                    "endRowIndex": fin + 1,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        })
    return peticiones
