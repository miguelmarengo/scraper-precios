"""Pruebas del «agente de Micaela» (agente.py), sin llamar a ningún servidor real.

Se reemplaza `agente.requests.post` por un doble que devuelve respuestas fabricadas,
y se comprueba que el payload que arma sea correcto, que el resultado se ordene por
puntaje, y que los errores (sin llave, sin criterio, HTTP 401/429, JSON raro) se
conviertan en `ErrorAgente` con un mensaje entendible.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agente  # noqa: E402
from scraper.core import Producto  # noqa: E402

fallos = []


def check(cond, etiqueta, extra=""):
    print(("  ok   " if cond else "  FALLA") + f"  {etiqueta}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        fallos.append(etiqueta)


class RespuestaFalsa:
    def __init__(self, status_code=200, cuerpo=None, texto=""):
        self.status_code = status_code
        self._cuerpo = cuerpo or {}
        self.text = texto

    def json(self):
        return self._cuerpo


def _cuerpo_ok(resultados):
    return {"choices": [{"message": {"content": json.dumps({"resultados": resultados})}}]}


productos = [
    Producto(nombre="Sillón Oslo", variante="Blanco", precio="12999.00", material="lino"),
    Producto(nombre="Sillón Tokio", variante="Concreto", precio="15999.00", material="concreto y madera"),
    Producto(nombre="Sillón Roma", variante="Rojo", precio="8999.00", material="terciopelo"),
]

llamadas = []


def _post_fabricado(url, headers=None, json=None, timeout=None):  # noqa: A002 - firma de requests.post
    llamadas.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
    return _post_fabricado.siguiente


# ------------------------------------------------------------------ sin criterio / sin llave
print("\n[1] Validaciones antes de llamar a ningún servidor")
try:
    agente.curar(productos, "", llave="sk-lo-que-sea")
    check(False, "sin criterio debe fallar")
except agente.ErrorAgente:
    check(True, "sin criterio, ErrorAgente claro")

try:
    agente.curar([], "los más elegantes", llave="sk-lo-que-sea")
    check(False, "sin productos debe fallar")
except agente.ErrorAgente:
    check(True, "sin productos, ErrorAgente claro")

os.environ.pop("OPENAI_API_KEY", None)
try:
    agente.curar(productos, "los más elegantes", llave="")
    check(False, "sin llave configurada debe fallar")
except agente.ErrorAgente as e:
    check("llave" in str(e).lower(), "sin llave, el mensaje menciona la llave", str(e))

check(agente.hay_agente("") is False, "hay_agente() es falso sin llave")
check(agente.hay_agente("sk-abc") is True, "hay_agente() es verdadero con una llave a mano")

# ------------------------------------------------------------------ payload y orden
print("\n[2] Se manda un producto por índice y el resultado sale ordenado por puntaje")
agente.requests.post = _post_fabricado
_post_fabricado.siguiente = RespuestaFalsa(200, _cuerpo_ok([
    {"indice": 0, "puntaje": 40, "razon": "Es blanco, no combina con el criterio."},
    {"indice": 1, "puntaje": 95, "razon": "Concreto y madera: justo lo que pediste."},
    {"indice": 2, "puntaje": 70, "razon": "Terciopelo rojo, llamativo pero no minimalista."},
]))

resultado = agente.curar(productos, "estilo minimalista, concreto, líneas limpias", llave="sk-prueba")

check(len(llamadas) == 1, "se hizo una sola llamada http")
enviado = llamadas[0]["json"]
check(enviado["messages"][1]["role"] == "user", "el segundo mensaje es del usuario")
cuerpo_usuario = json.loads(enviado["messages"][1]["content"])
check(cuerpo_usuario["criterio"] == "estilo minimalista, concreto, líneas limpias", "el criterio llega tal cual")
check(len(cuerpo_usuario["productos"]) == 3, "van los 3 productos", str(cuerpo_usuario["productos"]))
check(cuerpo_usuario["productos"][1]["nombre"] == "Sillón Tokio", "cada producto lleva su índice correcto")
check(llamadas[0]["headers"]["Authorization"] == "Bearer sk-prueba", "la llave se manda como Bearer token")

check(resultado["evaluados"] == 3, "evaluó los 3 productos")
check(resultado["recortado"] is False, "no hizo falta recortar la lista")
check([r["indice"] for r in resultado["resultados"]] == [1, 2, 0], "ordenado de mayor a menor puntaje",
      str(resultado["resultados"]))
check(resultado["resultados"][0]["puntaje"] == 95, "el puntaje más alto queda primero")

# ------------------------------------------------------------------ recorte por max_productos
print("\n[3] Se recorta a max_productos y se avisa")
_post_fabricado.siguiente = RespuestaFalsa(200, _cuerpo_ok([
    {"indice": 0, "puntaje": 10, "razon": "..."},
    {"indice": 1, "puntaje": 20, "razon": "..."},
]))
resultado2 = agente.curar(productos, "cualquier cosa", llave="sk-prueba", max_productos=2)
check(resultado2["evaluados"] == 2, "solo evaluó los primeros 2")
check(resultado2["recortado"] is True, "avisa que hubo recorte")

# ------------------------------------------------------------------ errores http
print("\n[4] Errores del servidor se traducen a mensajes claros")
_post_fabricado.siguiente = RespuestaFalsa(401, {}, "unauthorized")
try:
    agente.curar(productos, "algo", llave="sk-mala")
    check(False, "401 debe fallar")
except agente.ErrorAgente as e:
    check("válida" in str(e).lower() or "valida" in str(e).lower(), "401 → mensaje sobre la llave", str(e))

_post_fabricado.siguiente = RespuestaFalsa(429, {}, "rate limited")
try:
    agente.curar(productos, "algo", llave="sk-prueba")
    check(False, "429 debe fallar")
except agente.ErrorAgente as e:
    check("satur" in str(e).lower() or "cuota" in str(e).lower(), "429 → mensaje sobre saturación/cuota", str(e))

# ------------------------------------------------------------------ respuesta rara
print("\n[5] Un JSON de respuesta corrupto no tumba la app")
_post_fabricado.siguiente = RespuestaFalsa(200, {"choices": [{"message": {"content": "esto no es json"}}]})
try:
    agente.curar(productos, "algo", llave="sk-prueba")
    check(False, "JSON corrupto debe fallar con ErrorAgente")
except agente.ErrorAgente:
    check(True, "JSON corrupto → ErrorAgente, no una excepción cruda")

# índices fuera de rango o inválidos se ignoran sin tronar
_post_fabricado.siguiente = RespuestaFalsa(200, _cuerpo_ok([
    {"indice": 0, "puntaje": 50, "razon": "ok"},
    {"indice": 99, "puntaje": 10, "razon": "fuera de rango"},
    {"indice": "no-es-numero", "puntaje": 10, "razon": "índice inválido"},
]))
resultado3 = agente.curar(productos, "algo", llave="sk-prueba")
check(len(resultado3["resultados"]) == 1, "los índices inválidos o fuera de rango se descartan",
      str(resultado3["resultados"]))

print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron:")
    for f in fallos:
        print("  -", f)
    raise SystemExit(1)
print("Todas las pruebas pasaron.")
