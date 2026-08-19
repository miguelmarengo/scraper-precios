"""El «agente de Micaela»: un asistente de IA opcional que le pone un
puntaje y una razón a cada producto ya extraído, según un gusto, una
persona o un criterio que tú describas — «los que elegiría un arquitecto
minimalista», «los que usaría un electricista experto», «los que se ven
más frescos».

Importante, para no generar falsas expectativas:

- No analiza fotos ni prueba productos físicamente. Razona únicamente
  sobre el texto que el scraper ya extrajo (nombre, descripción, material,
  características, precio). Si ese texto no alcanza para decidir con
  certeza (por ejemplo, qué tan fresca está una fruta), se le pide que lo
  diga en la razón en vez de inventar.
- Es una opinión generada por IA, no una garantía ni un hecho verificado.
- Usa tu propia llave de API (OpenAI u otro proveedor compatible) — el
  costo de cada consulta corre por tu cuenta, y los textos de los
  productos se envían al servidor de ese proveedor.
"""

from __future__ import annotations

import json
import os

import requests

BASE_URL_POR_DEFECTO = "https://api.openai.com/v1"
MODELO_POR_DEFECTO = "gpt-4o-mini"
MAX_PRODUCTOS_POR_DEFECTO = 60
LIMITE_TEXTO = 220


class ErrorAgente(RuntimeError):
    pass


def _secreto(nombre: str) -> str:
    try:
        import streamlit as st

        valor = st.secrets.get(nombre, "")
        return str(valor) if valor else ""
    except Exception:
        return ""


def llave_configurada(llave: str | None = None) -> str:
    """La llave puede venir escrita a mano (esta sesión), de una variable de
    entorno (Docker) o de st.secrets. En ese orden de prioridad."""
    if llave and llave.strip():
        return llave.strip()
    return _secreto("openai_api_key") or os.environ.get("OPENAI_API_KEY", "").strip()


def hay_agente(llave: str | None = None) -> bool:
    return bool(llave_configurada(llave))


def _recortar(texto, limite: int = LIMITE_TEXTO) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _producto_compacto(indice: int, p) -> dict:
    return {
        "indice": indice,
        "nombre": getattr(p, "nombre", ""),
        "variante": getattr(p, "variante", ""),
        "marca": getattr(p, "marca", ""),
        "categoria": getattr(p, "categoria", ""),
        "precio": getattr(p, "precio", ""),
        "color": getattr(p, "color", ""),
        "material": getattr(p, "material", ""),
        "caracteristicas": _recortar(getattr(p, "caracteristicas", "")),
        "descripcion": _recortar(getattr(p, "descripcion", "")),
    }


_SISTEMA = (
    "Eres el agente de curación de compras de una diseñadora de interiores. Te dan un "
    "criterio — puede ser el gusto de una persona real, un perfil profesional, o una cualidad "
    "como 'el más fresco' — y una lista de productos ya extraídos de una tienda en línea, cada "
    "uno con un índice. Para CADA producto de la lista, sin excepción, da un puntaje de 0 a 100 "
    "según qué tanto encaja con el criterio, y una razón de una sola frase, en español, concreta "
    "y honesta. Si el texto del producto no alcanza para decidir con certeza (por ejemplo, no se "
    "puede saber qué tan fresca está una fruta solo por su nombre y descripción), dilo en la "
    "razón en vez de inventar detalles que no están en los datos. No inventes productos que no "
    "estén en la lista. Responde ÚNICAMENTE con este JSON, sin texto adicional: "
    '{"resultados": [{"indice": 0, "puntaje": 87, "razon": "..."}, ...]} '
    "con exactamente un elemento por cada producto que te dieron."
)


def curar(
    productos: list,
    instruccion: str,
    *,
    llave: str | None = None,
    modelo: str | None = None,
    base_url: str | None = None,
    max_productos: int = MAX_PRODUCTOS_POR_DEFECTO,
    timeout: int = 60,
) -> dict:
    """Le pide al agente que puntúe (0-100) y explique en una frase, cada
    producto de `productos`, según `instruccion`.

    Devuelve {'evaluados': int, 'recortado': bool, 'resultados': [...]}\u2014
    `resultados` viene ordenado de mayor a menor puntaje, y cada elemento
    trae 'indice' (la posición del producto dentro de la lista recibida,
    ya recortada a `max_productos`), 'puntaje' y 'razon'.
    """
    instruccion = (instruccion or "").strip()
    if not instruccion:
        raise ErrorAgente("Escribe qué gusto, persona o criterio quieres que use el agente.")
    if not productos:
        raise ErrorAgente("No hay productos que evaluar todavía.")

    llave_final = llave_configurada(llave)
    if not llave_final:
        raise ErrorAgente(
            "Falta la llave del agente de IA. Pégala en «🤖 Agente de Micaela», en la barra lateral."
        )

    recortado = len(productos) > max_productos
    lote = list(productos[:max_productos])
    compactos = [_producto_compacto(i, p) for i, p in enumerate(lote)]

    payload = {
        "model": modelo or os.environ.get("AGENTE_MODELO", MODELO_POR_DEFECTO),
        "messages": [
            {"role": "system", "content": _SISTEMA},
            {"role": "user", "content": json.dumps(
                {"criterio": instruccion, "productos": compactos}, ensure_ascii=False,
            )},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    url_base = (base_url or os.environ.get("AGENTE_BASE_URL", BASE_URL_POR_DEFECTO)).rstrip("/")

    try:
        resp = requests.post(
            f"{url_base}/chat/completions",
            headers={"Authorization": f"Bearer {llave_final}", "Content-Type": "application/json"},
            json=payload, timeout=timeout,
        )
    except requests.RequestException as e:
        raise ErrorAgente(f"No pude contactar al agente: {e}") from e

    if resp.status_code == 401:
        raise ErrorAgente("La llave del agente no es válida. Revísala en la barra lateral.")
    if resp.status_code == 429:
        raise ErrorAgente("El agente está saturado o se acabó tu cuota. Intenta en un momento.")
    if resp.status_code >= 400:
        raise ErrorAgente(f"El agente respondió con un error ({resp.status_code}): {resp.text[:300]}")

    try:
        contenido = resp.json()["choices"][0]["message"]["content"]
        crudos = json.loads(contenido)["resultados"]
    except Exception as e:
        raise ErrorAgente(f"El agente respondió algo que no pude leer: {e}") from e

    resultados = []
    for r in crudos:
        try:
            indice = int(r["indice"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= indice < len(lote)):
            continue
        try:
            puntaje = max(0, min(100, round(float(r.get("puntaje", 0)))))
        except (TypeError, ValueError):
            puntaje = 0
        resultados.append({"indice": indice, "puntaje": puntaje, "razon": str(r.get("razon", "")).strip()})
    resultados.sort(key=lambda r: r["puntaje"], reverse=True)

    return {"evaluados": len(lote), "recortado": recortado, "resultados": resultados}
