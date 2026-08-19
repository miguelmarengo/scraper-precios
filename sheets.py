"""Escritura directa a Google Sheets con una cuenta de servicio.

Necesita un archivo JSON de credenciales (ver README.md, sección "Google").
"""

from __future__ import annotations

import os
import re
from datetime import datetime

ALCANCES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

RUTA_CREDENCIALES_POR_DEFECTO = os.path.expanduser("~/.config/scraper-precios/credenciales.json")


class ErrorSheets(RuntimeError):
    pass


def ruta_credenciales(ruta: str | None = None) -> str:
    ruta = ruta or os.environ.get("GOOGLE_CREDENCIALES") or RUTA_CREDENCIALES_POR_DEFECTO
    return os.path.expanduser(ruta)


def _credenciales_en_secrets() -> dict | None:
    """En Streamlit Community Cloud no hay disco persistente para un archivo propio:
    la cuenta de servicio se guarda como "Secret" (TOML) bajo la llave
    [gcp_service_account]. Localmente sigue funcionando el archivo de siempre."""
    try:
        import streamlit as st

        datos = st.secrets.get("gcp_service_account")
        return dict(datos) if datos else None
    except Exception:
        return None


def hay_credenciales(ruta: str | None = None) -> bool:
    return _credenciales_en_secrets() is not None or os.path.isfile(ruta_credenciales(ruta))


def email_de_servicio(ruta: str | None = None) -> str:
    secretos = _credenciales_en_secrets()
    if secretos:
        return secretos.get("client_email", "")

    import json

    p = ruta_credenciales(ruta)
    if not os.path.isfile(p):
        return ""
    try:
        with open(p) as fh:
            return json.load(fh).get("client_email", "")
    except Exception:
        return ""


def _cliente(ruta: str | None = None):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as e:
        raise ErrorSheets(
            "Faltan las librerías de Google. Instálalas con:\n"
            "    pip install gspread google-auth"
        ) from e

    secretos = _credenciales_en_secrets()
    if secretos:
        creds = Credentials.from_service_account_info(secretos, scopes=ALCANCES)
        return gspread.authorize(creds)

    p = ruta_credenciales(ruta)
    if not os.path.isfile(p):
        raise ErrorSheets(
            f"No encontré el archivo de credenciales en:\n    {p}\n\n"
            "Sigue la sección 'Google' del README para crear la cuenta de servicio."
        )
    creds = Credentials.from_service_account_file(p, scopes=ALCANCES)
    return gspread.authorize(creds)


def _abrir_libro(gc, destino: str, compartir_con: str = ""):
    """destino puede ser una URL, un ID o un nombre. Si va vacío, crea uno nuevo."""
    destino = (destino or "").strip()

    if not destino:
        titulo = f"Precios scrapeados {datetime.now():%Y-%m-%d %H:%M}"
        libro = gc.create(titulo)
        if compartir_con:
            libro.share(compartir_con, perm_type="user", role="writer", notify=False)
        return libro, True

    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", destino)
    if m:
        return gc.open_by_key(m.group(1)), False
    if re.fullmatch(r"[a-zA-Z0-9-_]{30,}", destino):
        return gc.open_by_key(destino), False

    try:
        return gc.open(destino), False
    except Exception:
        libro = gc.create(destino)
        if compartir_con:
            libro.share(compartir_con, perm_type="user", role="writer", notify=False)
        return libro, True


def listar_hojas(ruta_creds: str | None = None) -> list[dict]:
    """Todas las hojas de cálculo que este robot ha creado o a las que tiene
    acceso — el "historial" de la app. No hace falta guardar nada aparte:
    Google Drive ya sabe qué hojas existen, así que esto siempre está al día
    aunque cambies de computadora o se reinicie el servidor."""
    gc = _cliente(ruta_creds)
    try:
        archivos = gc.list_spreadsheet_files()
    except Exception as e:
        raise ErrorSheets(f"No pude leer tu Google Drive: {e}") from e

    archivos = sorted(archivos, key=lambda a: a.get("modifiedTime", ""), reverse=True)
    return [
        {
            "id": a["id"],
            "nombre": a.get("name") or "(sin nombre)",
            "url": f"https://docs.google.com/spreadsheets/d/{a['id']}",
            "modificado": a.get("modifiedTime", ""),
        }
        for a in archivos
        if a.get("id")
    ]


def leer_hoja(destino: str, pestana: str, ruta_creds: str | None = None) -> dict:
    """Lee la pestaña tal cual está, conservando las fórmulas (=IMAGE) intactas.

    Devuelve {'libro','hoja','encabezado','filas','existe'}.
    """
    if not (destino or "").strip():
        raise ErrorSheets(
            "Para sincronizar necesito la URL de tu hoja. Pégala en «Tu hoja de Google»."
        )
    return _leer_o_crear(destino, pestana, "", ruta_creds)


def leer_o_crear_hoja(
    destino: str, pestana: str, *, compartir_con: str = "", ruta_creds: str | None = None
) -> dict:
    """Como `leer_hoja`, pero si `destino` viene vacío crea una hoja nueva en
    vez de exigir la URL — pensado para el modo «comparar», donde la primera
    vez todavía no existe ningún tablero."""
    return _leer_o_crear(destino, pestana, compartir_con, ruta_creds)


def _leer_o_crear(destino: str, pestana: str, compartir_con: str, ruta_creds: str | None) -> dict:
    import gspread

    gc = _cliente(ruta_creds)
    libro, _ = _abrir_libro(gc, destino, compartir_con)

    try:
        hoja = libro.worksheet(pestana)
    except gspread.WorksheetNotFound:
        return {"libro": libro, "hoja": None, "encabezado": [], "filas": [], "existe": False}

    # value_render_option="FORMULA" es clave: sin eso, las celdas con =IMAGE()
    # se leerían vacías y perderías las fotos al reescribir.
    valores = hoja.get_values(value_render_option="FORMULA")
    encabezado = valores[0] if valores else []
    filas = valores[1:] if len(valores) > 1 else []
    return {"libro": libro, "hoja": hoja, "encabezado": encabezado, "filas": filas, "existe": True}


def aplicar_plan(contexto: dict, plan, *, respaldar: bool = True, pestana: str = "Productos") -> dict:
    """Escribe el plan de sincronización y pinta el semáforo."""
    import gspread

    from sincronizar import peticiones_de_color

    libro = contexto["libro"]
    hoja = contexto["hoja"]

    if hoja is None:
        hoja = libro.add_worksheet(title=pestana, rows=len(plan.filas) + 20, cols=len(plan.encabezado) + 2)

    # Copia de seguridad de lo que había, por si algo sale mal.
    if respaldar and contexto.get("filas"):
        titulo = "Respaldo (antes de sincronizar)"
        try:
            try:
                respaldo = libro.worksheet(titulo)
                respaldo.clear()
            except gspread.WorksheetNotFound:
                respaldo = libro.add_worksheet(
                    title=titulo, rows=len(contexto["filas"]) + 20, cols=max(len(contexto["encabezado"]), 5)
                )
            previo = [contexto["encabezado"]] + contexto["filas"]
            respaldo.update(values=previo, range_name="A1", value_input_option="USER_ENTERED")
        except Exception:
            pass  # el respaldo es un extra; que falle no debe frenar la sincronización

    tabla = plan.tabla
    filas_necesarias = len(tabla) + 10
    columnas = len(plan.encabezado)

    hoja.clear()
    if hoja.row_count < filas_necesarias:
        hoja.add_rows(filas_necesarias - hoja.row_count)
    if hoja.col_count < columnas:
        hoja.add_cols(columnas - hoja.col_count)

    hoja.update(values=tabla, range_name="A1", value_input_option="USER_ENTERED")
    hoja.freeze(rows=1)
    try:
        hoja.format("A1:BZ1", {"textFormat": {"bold": True}})
    except Exception:
        pass

    peticiones = peticiones_de_color(hoja.id, plan.estados)
    for i in range(0, len(peticiones), 100):     # Google limita el tamaño del lote
        try:
            libro.batch_update({"requests": peticiones[i : i + 100]})
        except Exception:
            break

    _ajustar_para_fotos(libro, hoja, plan.encabezado, len(tabla))

    return {"url": libro.url, "titulo": libro.title, "pestana": hoja.title, **plan.resumen}


def aplicar_comparacion(
    contexto: dict, tabla: list[list], *, nuevos: int = 0, respaldar: bool = True,
    pestana: str = "Comparación",
) -> dict:
    """Escribe el tablero de comparación y resalta en verde los renglones
    que son producto nuevo en esta corrida (siempre van al final)."""
    import gspread

    libro = contexto["libro"]
    hoja = contexto["hoja"]

    if hoja is None:
        hoja = libro.add_worksheet(title=pestana, rows=len(tabla) + 20, cols=len(tabla[0]) + 5)

    if respaldar and contexto.get("filas"):
        titulo = "Respaldo (antes de comparar)"
        try:
            try:
                respaldo = libro.worksheet(titulo)
                respaldo.clear()
            except gspread.WorksheetNotFound:
                respaldo = libro.add_worksheet(
                    title=titulo, rows=len(contexto["filas"]) + 20, cols=max(len(contexto["encabezado"]), 5)
                )
            previo = [contexto["encabezado"]] + contexto["filas"]
            respaldo.update(values=previo, range_name="A1", value_input_option="USER_ENTERED")
        except Exception:
            pass

    filas_necesarias = len(tabla) + 10
    columnas = len(tabla[0]) if tabla else 0

    hoja.clear()
    if hoja.row_count < filas_necesarias:
        hoja.add_rows(filas_necesarias - hoja.row_count)
    if hoja.col_count < columnas:
        hoja.add_cols(columnas - hoja.col_count)

    hoja.update(values=tabla, range_name="A1", value_input_option="USER_ENTERED")
    hoja.freeze(rows=1)
    try:
        hoja.format("A1:BZ1", {"textFormat": {"bold": True}})
    except Exception:
        pass

    if nuevos:
        total_filas = len(tabla) - 1
        inicio = total_filas - nuevos
        try:
            libro.batch_update({"requests": [{
                "repeatCell": {
                    "range": {
                        "sheetId": hoja.id,
                        "startRowIndex": inicio + 1,
                        "endRowIndex": total_filas + 1,
                    },
                    "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.85, "green": 0.94, "blue": 0.85}}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            }]})
        except Exception:
            pass

    encabezado_final = tabla[0] if tabla else []
    _ajustar_para_fotos(libro, hoja, encabezado_final, len(tabla))
    _marcar_decision(libro, hoja, encabezado_final)
    _resaltar_mejor_precio(libro, hoja, encabezado_final, len(tabla))

    return {"url": libro.url, "titulo": libro.title, "pestana": hoja.title}


def _ajustar_para_fotos(libro, hoja, encabezado: list, filas: int) -> None:
    """Ensancha la columna de fotos y sube el alto de las filas para que
    las miniaturas de =IMAGE() se vean completas."""
    if "foto" not in encabezado:
        return
    col = encabezado.index("foto")
    peticiones = [
        {
            "updateDimensionProperties": {
                "range": {"sheetId": hoja.id, "dimension": "COLUMNS", "startIndex": col, "endIndex": col + 1},
                "properties": {"pixelSize": 120},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": hoja.id, "dimension": "ROWS", "startIndex": 1, "endIndex": max(filas, 2)},
                "properties": {"pixelSize": 95},
                "fields": "pixelSize",
            }
        },
    ]
    try:
        libro.batch_update({"requests": peticiones})
    except Exception:
        pass


def _marcar_decision(libro, hoja, encabezado: list) -> None:
    """Convierte la columna `decisión` (viendo / favorito / comprado) en un
    menú desplegable, para que decidir sea un clic y no escribir a mano."""
    from comparar import COL_DECISION, OPCIONES_DECISION

    if COL_DECISION not in encabezado:
        return
    col = encabezado.index(COL_DECISION)
    try:
        libro.batch_update({"requests": [{
            "setDataValidation": {
                "range": {
                    "sheetId": hoja.id,
                    "startRowIndex": 1,
                    "startColumnIndex": col,
                    "endColumnIndex": col + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": v} for v in OPCIONES_DECISION],
                    },
                    "showCustomUi": True,
                    "strict": False,
                },
            }
        }]})
    except Exception:
        pass


def _resaltar_mejor_precio(libro, hoja, encabezado: list, filas: int) -> None:
    """Pinta de dorado suave la columna `🏆 mejor precio`, para que la mejor
    oferta de cada renglón salte a la vista sin tener que leer columna por
    columna."""
    from comparar import COL_MEJOR

    if COL_MEJOR not in encabezado:
        return
    col = encabezado.index(COL_MEJOR)
    try:
        libro.batch_update({"requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": hoja.id,
                    "startRowIndex": 1,
                    "endRowIndex": max(filas, 2),
                    "startColumnIndex": col,
                    "endColumnIndex": col + 1,
                },
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.78},
                    "textFormat": {"bold": True},
                }},
                "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold",
            }
        }]})
    except Exception:
        pass


def escribir(
    tabla: list[list],
    *,
    destino: str = "",
    pestana: str = "Productos",
    modo: str = "reemplazar",
    compartir_con: str = "",
    ruta_creds: str | None = None,
) -> dict:
    """modo: 'reemplazar' | 'nueva' | 'agregar'."""
    if not tabla or len(tabla) < 2:
        raise ErrorSheets("No hay filas que escribir.")

    import gspread

    gc = _cliente(ruta_creds)
    libro, creado = _abrir_libro(gc, destino, compartir_con)

    encabezado, cuerpo = tabla[0], tabla[1:]
    filas_necesarias = len(tabla) + 10
    columnas = len(encabezado)

    if modo == "nueva":
        pestana = f"{pestana} {datetime.now():%Y-%m-%d %H%M}"

    try:
        hoja = libro.worksheet(pestana)
        nueva = False
    except gspread.WorksheetNotFound:
        hoja = libro.add_worksheet(title=pestana, rows=filas_necesarias, cols=columnas)
        nueva = True

    if modo == "agregar" and not nueva:
        existentes = hoja.get_all_values()
        if not existentes:
            # USER_ENTERED es indispensable aquí: sin él, Sheets guarda "=IMAGE(...)"
            # como texto literal en vez de evaluarlo, y la foto nunca aparece.
            hoja.update(values=tabla, range_name="A1", value_input_option="USER_ENTERED")
        else:
            hoja.append_rows(cuerpo, value_input_option="USER_ENTERED")
    else:
        hoja.clear()
        if hoja.row_count < filas_necesarias:
            hoja.add_rows(filas_necesarias - hoja.row_count)
        if hoja.col_count < columnas:
            hoja.add_cols(columnas - hoja.col_count)
        hoja.update(values=tabla, range_name="A1", value_input_option="USER_ENTERED")
        hoja.freeze(rows=1)
        try:
            hoja.format("A1:AZ1", {"textFormat": {"bold": True}})
        except Exception:
            pass
        _ajustar_para_fotos(libro, hoja, encabezado, len(tabla))

    # Limpia la pestaña vacía que Google crea por defecto.
    if creado:
        for h in libro.worksheets():
            if h.title in ("Sheet1", "Hoja 1", "Hoja1") and h.id != hoja.id:
                try:
                    libro.del_worksheet(h)
                except Exception:
                    pass

    return {
        "url": libro.url,
        "titulo": libro.title,
        "pestana": hoja.title,
        "creado": creado,
        "filas": len(cuerpo),
    }
