"""Interfaz web local. Se arranca con:  bash abrir.sh"""

from __future__ import annotations

import io
import os
import time
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

import agente
import comparar
import sheets
import textos
from scraper import COLUMNS, a_tabla, scrapear
from sincronizar import CAMBIO, COL_ESTADO, FALTANTE, IGUAL, NUEVO, construir_plan

NOMBRE_APP = "Scraper de Precios"
PROPIETARIA = "Micaela Marengo"
BIO_PROPIETARIA = (
    "Diseñadora de interiores · Ciudad de México — Nueva York · "
    "BFA en Diseño de Interiores, Pratt Institute"
)
SITIO_PROPIETARIA = "https://www.micaelamarengo.com/"

st.set_page_config(page_title=f"{NOMBRE_APP} · {PROPIETARIA}", page_icon="🛒", layout="wide")


def _encabezado(icono: str = "🛒") -> None:
    """Título + insignia con el nombre de la propietaria, en un solo bloque
    reutilizable (se ve igual en la pantalla de acceso y en la app)."""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.35rem;">
            <span style="font-size:2.3rem;line-height:1;">{icono}</span>
            <span style="font-size:2.1rem;font-weight:700;line-height:1;color:#1F2A24;">
                {NOMBRE_APP}
            </span>
        </div>
        <div style="display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap;">
            <span style="background:#16A34A1A;color:#16A34A;border:1px solid #16A34A55;
                         padding:0.2rem 0.75rem;border-radius:999px;font-size:0.85rem;
                         font-weight:600;letter-spacing:0.01em;">
                👤 {PROPIETARIA} · uso exclusivo
            </span>
            <span style="font-size:0.85rem;color:#5b6b62;">{BIO_PROPIETARIA}</span>
            <a href="{SITIO_PROPIETARIA}" target="_blank"
               style="font-size:0.85rem;font-weight:600;color:#16A34A;text-decoration:none;">
                🌐 Ver portafolio ↗
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _clave_de_acceso() -> str:
    """La contraseña puede venir de una variable de entorno (Docker) o de
    st.secrets (Streamlit Community Cloud). Si no se configura ninguna,
    la app queda abierta — pensado para uso local de confianza."""
    try:
        clave = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        clave = ""
    return clave or os.environ.get("APP_PASSWORD", "")


def _exigir_acceso() -> None:
    clave = _clave_de_acceso()
    if not clave or st.session_state.get("autenticado"):
        return

    _encabezado("🔒")
    st.write("")
    st.write("Esta herramienta es privada. Pide la contraseña a quien te la comparta.")

    with st.form("form_acceso"):
        intento = st.text_input("Contraseña", type="password", label_visibility="collapsed",
                                 placeholder="Contraseña")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if entrar:
        if intento == clave:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()


_exigir_acceso()

MODOS = ["sincronizar", "comparar", "reemplazar", "nueva", "agregar"]
NOMBRES_MODO = {
    "sincronizar": "Actualizar mi hoja, respetando lo que ya tiene",
    "comparar": "Comparar el mismo producto entre varias tiendas",
    "reemplazar": "Borrar la pestaña y escribirla de cero",
    "nueva": "Crear una pestaña nueva con la fecha",
    "agregar": "Pegar al final, para hacer historial",
}

# Presets de velocidad: tres decisiones ya tomadas, para que la mayoría de la
# gente no tenga que tocar sliders. Quien quiera control fino elige "Personalizado".
PRESETS = {
    "⚡ Rápido": dict(
        max_productos=100, detalle=False, prefiltrar=True, delay=0.3, workers=6,
        desc="Hasta 100 productos, sin abrir cada ficha. Ideal para explorar una tienda por primera vez.",
    ),
    "⚖️ Equilibrado": dict(
        max_productos=300, detalle=True, prefiltrar=True, delay=0.6, workers=4,
        desc="Hasta 300 productos con inventario, medidas y entrega. El punto medio para el uso diario.",
    ),
    "🔍 Completo": dict(
        max_productos=1500, detalle=True, prefiltrar=True, delay=0.8, workers=3,
        desc="Hasta 1500 productos, todo el detalle. Tarda más, pero no se escapa nada.",
    ),
}
NOMBRES_PRESET = list(PRESETS) + ["🎛️ Personalizado"]


def limpiar_resultados():
    for k in (
        "productos", "informe", "plan", "contexto", "plan_cmp", "contexto_cmp",
        "agente_tabla", "agente_meta",
    ):
        st.session_state.pop(k, None)


def _nombre_tienda_de(url: str) -> str:
    """Deriva un nombre de tienda legible a partir de su dominio, como
    valor inicial de la columna en el modo «comparar» (el usuario lo puede
    cambiar)."""
    neto = urlparse(url if "//" in url else f"https://{url}").netloc
    base = neto.replace("www.", "").split(":")[0].split(".")[0]
    return base.capitalize() if base else "Tienda"


@st.cache_data(ttl=45, show_spinner="Buscando tus hojas en Google Drive…")
def _listar_hojas_cacheado(ruta_creds: str):
    return sheets.listar_hojas(ruta_creds)


# ═══════════════════════════════════════════════════ barra lateral
with st.sidebar:
    st.header("🔗 Conexión con Google")
    with st.expander("¿Por qué hace falta esto?"):
        st.markdown(textos.AYUDA_GOOGLE)

    ruta_creds = st.text_input(
        "Archivo de credenciales",
        value=sheets.RUTA_CREDENCIALES_POR_DEFECTO,
        help="La llave JSON que descargaste de Google Cloud.",
    )
    conectado = sheets.hay_credenciales(ruta_creds)
    if conectado:
        st.success("Credenciales encontradas", icon="✅")
        correo = sheets.email_de_servicio(ruta_creds)
        if correo:
            st.caption("Comparte tu hoja como **Editor** con este correo:")
            st.code(correo, language=None)
    else:
        st.warning("Todavía no encuentro el archivo. Puedes extraer y descargar en CSV sin él.", icon="⚠️")

    st.divider()
    st.header("🤖 Agente de Micaela")
    with st.expander("¿Qué hace y qué no?"):
        st.markdown(textos.AYUDA_AGENTE)

    llave_agente_entorno = agente.llave_configurada()
    if llave_agente_entorno:
        st.success("Agente listo — usando la llave configurada por variable de entorno.", icon="✅")
        llave_agente = llave_agente_entorno
    else:
        llave_agente = st.text_input(
            "Llave de OpenAI (opcional)", type="password", placeholder="sk-…",
            help="Solo se usa para pedirle su opinión al agente en la pestaña 5️⃣ Resultados. "
                 "Vive únicamente en esta sesión del navegador, no se guarda en ningún archivo.",
        )
        if llave_agente:
            st.caption("🔐 Guardada solo para esta sesión, no se escribe en disco.")
        else:
            st.caption("Sin llave, el resto de la app funciona igual; solo el agente queda apagado.")

    st.divider()
    st.header("⚙️ ¿Qué tan a fondo trabajo?")
    preset = st.radio(
        "Velocidad", NOMBRES_PRESET, index=1, horizontal=False, label_visibility="collapsed",
    )
    if preset == "🎛️ Personalizado":
        max_productos = st.number_input(
            "Máximo de resultados", 10, 5000, 300, step=50,
            help="Corta el trabajo cuando junta esta cantidad. Empieza con 50 para probar rápido.",
        )
        detalle = st.checkbox(
            "Abrir la ficha de cada producto", value=True,
            help="Es la única forma de obtener inventario exacto, tiempo de entrega y medidas "
                 "completas. Tarda más. Apágalo si solo te interesan nombres y precios.",
        )
        prefiltrar = st.checkbox(
            "Pre-filtrar por la dirección del producto", value=True,
            help="Con un filtro activo, descarta de entrada las fichas cuya liga no menciona "
                 "ninguna de tus palabras. Acelera muchísimo en tiendas grandes. Si la tienda usa "
                 "ligas con puros números, la app lo detecta y no lo aplica.",
        )
        delay = st.slider(
            "Pausa entre peticiones (segundos)", 0.0, 3.0, 0.6, 0.1,
            help="Súbela si la tienda empieza a rechazar peticiones (error 429).",
        )
        workers = st.slider(
            "Peticiones al mismo tiempo", 1, 12, 4,
            help="Bájala a 1 o 2 si la tienda es lenta o sensible.",
        )
    else:
        cfg = PRESETS[preset]
        max_productos, detalle = cfg["max_productos"], cfg["detalle"]
        prefiltrar, delay, workers = cfg["prefiltrar"], cfg["delay"], cfg["workers"]
        st.caption(cfg["desc"])

    st.divider()
    st.header("🛡️ Seguridad")
    robots = st.checkbox(
        "Respetar robots.txt", value=True,
        help="Es el archivo donde el sitio declara qué rutas pide que no se rastreen. "
             "Déjalo encendido.",
    )
    respaldar = st.checkbox(
        "Guardar respaldo antes de sincronizar", value=True,
        help="Copia el contenido anterior a una pestaña llamada «Respaldo».",
    )

# ═══════════════════════════════════════════════════ encabezado
_encabezado("🛒")
st.write("")
st.caption(
    "🟢 Conectado a Google — puedo escribir directo en tu hoja."
    if conectado else
    "⚪ Sin conexión a Google todavía — puedes extraer y descargar en CSV o Excel mientras la "
    "configuras (ábrela en la barra lateral izquierda)."
)
with st.expander("**¿Qué hace esta herramienta y cómo se usa?** — ábrelo si es tu primera vez", expanded=False):
    st.markdown(textos.QUE_HACE)

st.write("")
st.markdown(
    "##### Sigue las 5 pestañas en orden — cada una te dice exactamente qué hacer."
)
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ Tienda", "2️⃣ Filtrar", "3️⃣ Destino", "4️⃣ Extraer", "5️⃣ Resultados",
])

# ═══════════════════════════════════════════════════ 1 · tienda
with tab1:
    st.subheader("¿Qué tienda quieres revisar?")
    st.markdown("**Qué hacer aquí:** pega la dirección de la tienda. Nada más.")
    st.caption(
        "Puede ser la página principal o una categoría. La app detecta sola qué tecnología usa "
        "el sitio y elige la mejor forma de leer su catálogo."
    )
    url = st.text_input("Dirección de la tienda", placeholder="https://ejemplo.com", label_visibility="collapsed")
    if url.strip():
        st.success("Listo ✅ — ahora ve a la pestaña **2️⃣ Filtrar** (o salta directo a **4️⃣ Extraer**).")
    else:
        st.info("👉 Pega aquí la liga de la tienda para poder avanzar.")

# ═══════════════════════════════════════════════════ 2 · filtrar
with tab2:
    st.subheader("¿Qué te interesa? (opcional)")
    st.markdown(
        "**Qué hacer aquí:** escribe palabras para quedarte solo con lo que te importa. "
        "Si no escribes nada, se trae el catálogo completo."
    )
    st.caption(
        "Esto no solo recorta la lista: hace el trabajo mucho más rápido, porque descarta lo "
        "que no te interesa antes de abrir cada ficha."
    )
    filtro_txt = st.text_input(
        "Qué buscas",
        placeholder="sillones blancos     ·     verduras verdes     ·     sofa | loveseat -piel",
        label_visibility="collapsed",
    )
    with st.expander("Ver todas las formas de escribir el filtro"):
        st.markdown(textos.AYUDA_FILTRO)

    st.write("")
    st.markdown("**Filtros de precio y disponibilidad (también opcionales):**")
    f1, f2, f3 = st.columns([1, 1, 2])
    precio_min = f1.number_input("Precio mínimo", min_value=0.0, value=0.0, step=100.0, help="0 = sin mínimo")
    precio_max = f2.number_input("Precio máximo", min_value=0.0, value=0.0, step=100.0, help="0 = sin tope")
    with f3:
        st.write("")
        solo_disp = f3.checkbox("Solo los que están disponibles", value=False,
                                help="Descarta lo que la tienda marca como agotado.")
    st.info("Listo. Ve a la pestaña **3️⃣ Destino**, o salta directo a **4️⃣ Extraer**.")

# ═══════════════════════════════════════════════════ 3 · destino
with tab3:
    st.subheader("¿A dónde mando el resultado?")
    st.markdown(
        "**Qué hacer aquí:** nada, si solo quieres un archivo — siempre puedes descargar CSV o "
        "Excel en **5️⃣ Resultados**. Llena esto únicamente si además quieres que se escriba en "
        "un Google Sheet."
    )
    modo = st.radio(
        "Modo de escritura",
        MODOS,
        format_func=NOMBRES_MODO.get,
        label_visibility="collapsed",
    )
    st.info(textos.AYUDA_MODOS[modo])

    estrategia = "auto"
    tienda_cmp = ""

    if modo == "comparar":
        st.markdown("**📚 Tus hojas** — elige el tablero al que le agregas esta tienda, o crea uno nuevo.")
        NUEVO_TABLERO = "➕ Crear un tablero nuevo"
        hojas = []
        if conectado:
            try:
                hojas = _listar_hojas_cacheado(ruta_creds)
            except sheets.ErrorSheets as e:
                st.warning(f"No pude ver tus hojas todavía: {e}")
        else:
            st.warning("Conecta Google en la barra lateral para ver y elegir entre tus tableros.")

        h1, h2 = st.columns([5, 1])
        elegida = h1.selectbox(
            "Tablero de comparación",
            [NUEVO_TABLERO] + [h["nombre"] for h in hojas],
            label_visibility="collapsed",
        )
        if h2.button("🔄", help="Actualizar la lista de tus hojas", use_container_width=True):
            _listar_hojas_cacheado.clear()
            st.rerun()

        if elegida != NUEVO_TABLERO:
            info_hoja = next(h for h in hojas if h["nombre"] == elegida)
            destino = info_hoja["url"]
            st.caption(f"Se va a escribir en **{info_hoja['nombre']}**, pestaña «Comparación».")
        else:
            destino = ""
            st.caption("Se va a crear un tablero nuevo la primera vez que le des a Extraer.")

        with st.expander("¿No la ves en la lista? Pega la liga a mano"):
            manual = st.text_input(
                "Liga de la hoja", placeholder="https://docs.google.com/spreadsheets/d/…",
                label_visibility="collapsed",
            )
            if manual.strip():
                destino = manual.strip()

        tienda_cmp = st.text_input(
            "¿Cómo se llama esta tienda?",
            value=_nombre_tienda_de(url) if url.strip() else "",
            help="Así se va a llamar la columna de precio de esta corrida, por ejemplo «precio · Liverpool».",
        )
        with st.expander("¿Cómo decide que es «el mismo producto» en otra tienda?"):
            st.markdown(textos.AYUDA_COMPARAR)
        pestana = "Comparación"

    else:
        d1, d2 = st.columns([3, 1])
        destino = d1.text_input(
            "Tu hoja de Google",
            placeholder="https://docs.google.com/spreadsheets/d/…",
            help="Pega la URL completa de tu hoja. Si la dejas vacía (y no estás sincronizando), "
                 "se crea una hoja nueva.",
        )
        pestana = d2.text_input("Pestaña", value="Productos", help="El nombre de la pestaña dentro de tu hoja.")

        if modo == "sincronizar":
            with st.expander("Ver cómo se decide que un producto es «el mismo» de antes"):
                st.markdown(textos.AYUDA_EMPAREJAMIENTO)
            estrategia = st.selectbox(
                "Cómo emparejar con lo que ya tienes",
                ["auto", "sku", "url"],
                format_func={
                    "auto": "Automático — SKU y, si no hay, la liga (recomendado)",
                    "sku": "Solo el SKU",
                    "url": "Solo la liga del producto",
                }.get,
            )
            st.markdown("**Qué vas a ver en tu hoja:**")
            st.markdown(textos.LEYENDA)

    if modo not in ("sincronizar", "comparar"):
        compartir = st.text_input(
            "Si creo una hoja nueva, compártela con",
            placeholder="tucorreo@gmail.com",
            help="La hoja nace a nombre del robot. Escribe tu correo para que también llegue a tu Drive.",
        )
    elif modo == "comparar" and not destino.strip():
        compartir = st.text_input(
            "Como es un tablero nuevo, compártelo con",
            placeholder="tucorreo@gmail.com",
            help="El tablero nace a nombre del robot. Escribe tu correo para que también llegue a tu Drive.",
        )
    else:
        compartir = ""

    st.write("")
    st.info("Listo. Ve a la pestaña **4️⃣ Extraer** para empezar.")

# ═══════════════════════════════════════════════════ 4 · extraer
with tab4:
    st.subheader("Extraer")
    st.markdown("**Qué hacer aquí:** dale clic al botón. Es el único paso obligatorio.")
    st.caption("Nada se escribe en tu hoja todavía. Primero te enseño lo que encontré, en la pestaña **5️⃣ Resultados**.")

    if st.button("🚀 Extraer precios de la tienda", type="primary", use_container_width=True):
        if not url.strip():
            st.error("Falta la dirección de la tienda. Ve a la pestaña **1️⃣ Tienda**.")
        elif modo == "sincronizar" and not destino.strip():
            st.error("Para sincronizar necesito la URL de tu hoja. Ve a la pestaña **3️⃣ Destino**.")
        elif modo == "comparar" and not tienda_cmp.strip():
            st.error("Falta el nombre de esta tienda para la comparación. Ve a la pestaña **3️⃣ Destino**.")
        else:
            limpiar_resultados()
            barra = st.progress(0.0)
            estado = st.empty()
            inicio = time.time()
            ultimo = {"pct": 0.05}

            def progreso(mensaje, pct=None):
                if pct is not None:
                    ultimo["pct"] = min(max(pct, 0.0), 1.0)
                estado.info(f"⏱️ {time.time() - inicio:0.0f}s — {mensaje}")
                barra.progress(ultimo["pct"])

            try:
                with st.spinner("Leyendo la tienda…"):
                    productos, informe = scrapear(
                        url,
                        filtro=filtro_txt,
                        precio_min=precio_min or None,
                        precio_max=precio_max or None,
                        solo_disponibles=solo_disp,
                        max_productos=int(max_productos),
                        detalle_inventario=detalle,
                        respetar_robots=robots,
                        delay=float(delay),
                        workers=int(workers),
                        prefiltrar_urls=prefiltrar,
                        progreso=progreso,
                    )
                st.session_state["productos"] = productos
                st.session_state["informe"] = informe

                if modo == "sincronizar" and productos:
                    estado.info("Leyendo tu hoja para compararla… (todavía no escribo nada)")
                    contexto = sheets.leer_hoja(destino, pestana, ruta_creds)
                    plan = construir_plan(
                        contexto["encabezado"], contexto["filas"], productos, estrategia=estrategia
                    )
                    st.session_state["contexto"] = contexto
                    st.session_state["plan"] = plan
                elif modo == "comparar" and productos:
                    estado.info("Leyendo tu tablero de comparación… (todavía no escribo nada)")
                    contexto_cmp = sheets.leer_o_crear_hoja(
                        destino, pestana, compartir_con=compartir, ruta_creds=ruta_creds
                    )
                    plan_cmp = comparar.construir_comparacion(
                        contexto_cmp["encabezado"], contexto_cmp["filas"], productos, tienda_cmp
                    )
                    st.session_state["contexto_cmp"] = contexto_cmp
                    st.session_state["plan_cmp"] = plan_cmp
                barra.progress(1.0)
                estado.empty()
                transcurrido = time.time() - inicio
                st.toast(f"Listo en {transcurrido:0.0f}s: {len(productos)} producto(s) encontrados.", icon="✅")
                if productos:
                    st.success(
                        f"✅ Encontré {len(productos)} producto(s) en {transcurrido:0.0f}s. "
                        "Abre la pestaña **5️⃣ Resultados** para verlos."
                    )
                else:
                    st.warning("No encontré productos. Abre la pestaña **5️⃣ Resultados** para ver por qué.")
            except PermissionError as e:
                barra.empty(); estado.empty()
                st.error(str(e))
            except sheets.ErrorSheets as e:
                barra.empty(); estado.empty()
                st.warning(f"Extraje los productos, pero no pude leer tu hoja: {e}")
            except Exception as e:
                barra.empty(); estado.empty()
                st.error(f"Algo falló: {e}")

# ═══════════════════════════════════════════════════ 5 · resultados
with tab5:
    productos = st.session_state.get("productos")
    informe = st.session_state.get("informe")
    plan = st.session_state.get("plan")
    contexto = st.session_state.get("contexto")
    plan_cmp = st.session_state.get("plan_cmp")
    contexto_cmp = st.session_state.get("contexto_cmp")

    if productos is None:
        st.info(
            "Todavía no hay nada que mostrar aquí. Ve a **1️⃣ Tienda**, pega la liga, y dale clic "
            "al botón en **4️⃣ Extraer**."
        )
    elif not productos:
        if informe and informe.get("filtro_activo"):
            st.warning(
                "Encontré la tienda, pero ningún producto pasó el filtro. Prueba con menos palabras "
                "(por ejemplo solo «sillon») o quita el filtro para ver primero qué trae el catálogo."
            )
        else:
            st.warning(
                "No encontré productos con datos estructurados. Suele pasar cuando el catálogo se "
                "arma con JavaScript o está detrás de un login."
            )

    if productos:
        st.subheader("Lo que encontré en la tienda")
        df = pd.DataFrame([p.as_row() for p in productos], columns=COLUMNS)

        c = st.columns(5)
        c[0].metric("Plataforma", informe["plataforma"])
        c[1].metric("Productos", informe["filas"])
        c[2].metric("Con precio", informe["con_precio"])
        c[3].metric("Con foto", informe["con_foto"])
        c[4].metric("Con medidas", informe["con_medidas"])

        # ─────────────────────────────────── mejores ofertas (si hay descuentos)
        descuentos = pd.to_numeric(df["descuento_pct"], errors="coerce")
        ofertas = df.loc[descuentos[descuentos > 0].sort_values(ascending=False).index].head(5).copy()
        if not ofertas.empty:
            for col in ("precio", "precio_lista", "descuento_pct"):
                ofertas[col] = pd.to_numeric(ofertas[col], errors="coerce")
            st.markdown(f"##### 🔥 {len(ofertas)} de las mejores ofertas de esta corrida")
            st.dataframe(
                ofertas.drop(columns=["foto"]),
                use_container_width=True, height=230, hide_index=True,
                column_order=["imagen", "nombre", "variante", "precio", "precio_lista", "descuento_pct"],
                column_config={
                    "imagen": st.column_config.ImageColumn("foto", width="small"),
                    "descuento_pct": st.column_config.NumberColumn("descuento", format="%.0f%%"),
                    "precio": st.column_config.NumberColumn("precio"),
                    "precio_lista": st.column_config.NumberColumn("antes"),
                },
            )

        vista = df.drop(columns=["foto"])

        bcol1, bcol2 = st.columns([2, 1])
        busqueda = bcol1.text_input(
            "🔎 Buscar en estos resultados", placeholder="ej. blanco, madera, SO-142…",
            help="Filtra por nombre, variante, SKU, marca, categoría, color, material o características.",
        )
        orden_opciones = {
            "Como se encontraron": None,
            "Mayor descuento primero": ("descuento_pct", False),
            "Menor precio primero": ("precio", True),
            "Mayor precio primero": ("precio", False),
        }
        orden_sel = bcol2.selectbox("Ordenar por", list(orden_opciones.keys()))

        if busqueda.strip():
            columnas_busqueda = [
                c for c in ["nombre", "variante", "sku", "marca", "categoria", "color", "material", "caracteristicas"]
                if c in vista.columns
            ]
            coincide = vista[columnas_busqueda].apply(
                lambda col: col.astype(str).str.contains(busqueda.strip(), case=False, na=False, regex=False)
            ).any(axis=1)
            vista = vista[coincide]

        campo_orden = orden_opciones[orden_sel]
        if campo_orden:
            columna, ascendente = campo_orden
            vista = (
                vista.assign(_orden=pd.to_numeric(vista[columna], errors="coerce"))
                .sort_values("_orden", ascending=ascendente, na_position="last")
                .drop(columns="_orden")
            )

        st.dataframe(
            vista, use_container_width=True, height=380,
            column_order=["imagen"] + [x for x in vista.columns if x != "imagen"],
            column_config={
                "imagen": st.column_config.ImageColumn("foto", width="small"),
                "url_producto": st.column_config.LinkColumn("liga", display_text="abrir"),
            },
        )
        st.caption(f"Mostrando {len(vista)} de {len(df)} productos.")
        with st.expander("¿Qué significa cada columna?"):
            st.markdown(textos.AYUDA_COLUMNAS)
        with st.expander("¿Por qué algunas celdas salen vacías?"):
            st.markdown(textos.AYUDA_LIMITES)

        dominio = (urlparse(informe["url"]).netloc or "tienda").replace("www.", "").split(":")[0]
        sello = datetime.now().strftime("%Y%m%d-%H%M")
        nombre_base = f"precios-{dominio}-{sello}"
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Productos")
        b1, b2, _ = st.columns([1, 1, 3])
        b1.download_button("⬇️ Descargar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           f"{nombre_base}.csv", "text/csv", use_container_width=True)
        b2.download_button("⬇️ Descargar Excel", buffer.getvalue(), f"{nombre_base}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

        st.divider()

        # ─────────────────────────────────────────── agente de ia (opcional)
        st.markdown("##### 🤖 Pregúntale al agente de Micaela")
        st.caption(
            "Describe un gusto, una persona o un criterio, y le pone un puntaje del 0 al 100 y "
            "una razón corta a cada producto de la lista de arriba (respeta tu búsqueda y orden "
            "actuales). Es una opinión de IA a partir del texto ya extraído, no analiza fotos ni "
            "prueba productos — revisa tú antes de decidir, sobre todo en cosas perecederas."
        )
        col_pregunta, col_boton = st.columns([3, 1])
        instruccion_agente = col_pregunta.text_input(
            "¿Qué le pido?", label_visibility="collapsed",
            placeholder="ej. Los que elegiría Tadao Ando · Los que usaría un electricista experto · Los más frescos",
        )
        llave_lista = agente.hay_agente(llave_agente)
        preguntar = col_boton.button(
            "✨ Preguntar", use_container_width=True,
            disabled=not (instruccion_agente.strip() and llave_lista),
        )
        if not llave_lista:
            st.caption("🔑 Pega una llave de IA en la barra lateral, en **🤖 Agente de Micaela**, para activar esto.")

        if preguntar:
            productos_vista = [productos[i] for i in vista.index]
            try:
                with st.spinner("El agente de Micaela está pensando…"):
                    resultado_agente = agente.curar(productos_vista, instruccion_agente, llave=llave_agente)
                filas_agente = [
                    {
                        "imagen": productos_vista[r["indice"]].imagen,
                        "nombre": productos_vista[r["indice"]].nombre,
                        "variante": productos_vista[r["indice"]].variante,
                        "precio": productos_vista[r["indice"]].precio,
                        "🤖 puntaje": r["puntaje"],
                        "🤖 por qué": r["razon"],
                        "url_producto": productos_vista[r["indice"]].url_producto,
                    }
                    for r in resultado_agente["resultados"]
                ]
                st.session_state["agente_tabla"] = pd.DataFrame(filas_agente)
                st.session_state["agente_meta"] = {
                    "instruccion": instruccion_agente,
                    "evaluados": resultado_agente["evaluados"],
                    "recortado": resultado_agente["recortado"],
                }
                st.toast("El agente terminó de opinar 🤖", icon="✨")
            except agente.ErrorAgente as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"No pude preguntarle al agente: {e}")

        agente_tabla = st.session_state.get("agente_tabla")
        agente_meta = st.session_state.get("agente_meta")
        if agente_tabla is not None and agente_meta:
            st.markdown(f"**Para:** _{agente_meta['instruccion']}_")
            if agente_meta["recortado"]:
                st.caption(
                    f"⚠️ Evalué los primeros {agente_meta['evaluados']} productos de esta vista; "
                    "acorta tu búsqueda si quieres que cubra el resto."
                )
            st.dataframe(
                agente_tabla, use_container_width=True, height=320, hide_index=True,
                column_config={
                    "imagen": st.column_config.ImageColumn("foto", width="small"),
                    "precio": st.column_config.NumberColumn("precio"),
                    "🤖 puntaje": st.column_config.ProgressColumn("🤖 puntaje", min_value=0, max_value=100, format="%d"),
                    "url_producto": st.column_config.LinkColumn("liga", display_text="abrir"),
                },
            )
            st.caption(
                "Opinión generada por IA, no una garantía — el agente no ve fotos ni prueba "
                "productos, solo razona sobre el texto extraído."
            )

        st.divider()

        # ─────────────────────────────────────────── sincronización
        if modo == "sincronizar" and plan is not None:
            st.subheader("Qué va a pasar en tu hoja")
            r = plan.resumen
            st.caption(
                f"Tu hoja tenía **{r['previos']}** renglones. Encontré **{r['extraidos']}** productos "
                f"en la tienda. Después de aplicar, tu hoja quedaría con **{r['total']}** renglones."
            )

            m = st.columns(4)
            m[0].metric("🟢 Nuevos", r["nuevos"], help="No estaban; se agregan al final.")
            m[1].metric("🟡 Cambiaron", r["cambiados"], help="Se actualizan y te anoto qué se movió.")
            m[2].metric("🔴 No encontrados", r["faltantes"], help="Se quedan tal cual, sin tocarse.")
            m[3].metric("⚪ Sin cambios", r["iguales"], help="Solo se les actualiza la fecha.")

            if plan.aviso:
                st.warning(plan.aviso)
            if r["columnas_propias"]:
                st.success(
                    "Tus columnas se conservan intactas: " + ", ".join(f"`{x}`" for x in r["columnas_propias"])
                )
            if r["faltantes"] and informe.get("filtro_activo"):
                st.info(
                    "Traes un filtro activo. Los renglones en rojo pueden ser simplemente productos "
                    "que este filtro ya no pide, no necesariamente productos que desaparecieron."
                )

            previa = pd.DataFrame(plan.filas, columns=plan.encabezado)
            elegido = st.selectbox(
                "Ver en la vista previa",
                ["Todo", NUEVO, CAMBIO, FALTANTE, IGUAL],
                help="Filtra la tabla de abajo para revisar un grupo a la vez.",
            )
            if elegido != "Todo":
                previa = previa[previa[COL_ESTADO] == elegido]

            st.dataframe(
                previa.drop(columns=["foto"], errors="ignore"),
                use_container_width=True, height=380,
                column_config={
                    "imagen": st.column_config.ImageColumn("foto", width="small"),
                    "url_producto": st.column_config.LinkColumn("liga", display_text="abrir"),
                    "cambios": st.column_config.TextColumn("cambios", width="large"),
                },
            )
            st.caption(f"Mostrando {len(previa)} de {len(plan.filas)} renglones.")

            st.warning(
                "Al aplicar, la pestaña se reescribe completa con estos renglones. Se conserva todo "
                "tu contenido, pero las columnas se reordenan (control primero, luego los datos, "
                "luego las tuyas). Si tienes fórmulas que apuntan a celdas concretas de esta pestaña, "
                "revísalas después."
                + (" Antes de escribir guardo una copia en la pestaña «Respaldo»." if respaldar else
                   " **Tienes el respaldo apagado.**")
            )

            if st.button("Aplicar a mi hoja", type="primary"):
                try:
                    with st.spinner("Escribiendo y pintando el semáforo…"):
                        res = sheets.aplicar_plan(contexto, plan, respaldar=respaldar, pestana=pestana)
                    st.toast("Tu hoja quedó actualizada.", icon="✅")
                    st.success(
                        f"Listo. {res['nuevos']} nuevos, {res['cambiados']} actualizados, "
                        f"{res['faltantes']} marcados en rojo, {res['iguales']} sin cambios."
                    )
                    st.link_button("Abrir mi hoja", res["url"])
                    limpiar_resultados()
                except sheets.ErrorSheets as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"No pude escribir en tu hoja: {e}")

        # ─────────────────────────────────────────── comparación entre tiendas
        elif modo == "comparar" and plan_cmp is not None:
            st.subheader(f"Comparación: agregando «{plan_cmp.tienda}» a tu tablero")
            r = plan_cmp.resumen
            st.caption(
                f"Tu tablero tenía **{r['renglones_previos']}** producto(s). Esta corrida trajo "
                f"**{r['extraidos']}** de **{plan_cmp.tienda}** ({r['exactos']} coincidieron solos "
                "por nombre)."
            )

            confirmados: dict[int, bool] = {}
            if plan_cmp.candidatos:
                st.markdown("**¿Alguno de estos es el mismo producto que ya tenías?**")
                st.caption(
                    "El nombre se parece pero no es idéntico, así que no los uní solos. Marca la "
                    "casilla de los que **sí** sean el mismo producto; el resto se agrega como "
                    "renglón nuevo."
                )
                df_revisar = pd.DataFrame([{
                    "Es el mismo": False,
                    f"Nuevo en {plan_cmp.tienda}": c.nombre_nuevo + (f" · {c.variante_nuevo}" if c.variante_nuevo else ""),
                    "Se parece a (ya en tu tablero)": c.nombre_existente + (f" · {c.variante_existente}" if c.variante_existente else ""),
                    "Qué tan parecido": f"{c.similitud:.0%}",
                    "_indice": c.indice_producto,
                } for c in plan_cmp.candidatos])
                editado = st.data_editor(
                    df_revisar.drop(columns=["_indice"]),
                    use_container_width=True, hide_index=True, key="editor_comparacion",
                    disabled=[f"Nuevo en {plan_cmp.tienda}", "Se parece a (ya en tu tablero)", "Qué tan parecido"],
                )
                for indice_fila, marcado in zip(df_revisar["_indice"], editado["Es el mismo"]):
                    confirmados[int(indice_fila)] = bool(marcado)
            else:
                st.caption("No hubo coincidencias dudosas que revisar en esta corrida.")

            tabla_final, resumen_final = plan_cmp.tabla(confirmados)
            m = st.columns(3)
            m[0].metric("✅ Con precio actualizado", resumen_final["actualizados_finales"])
            m[1].metric("🆕 Nuevos en el tablero", resumen_final["nuevos_finales"])
            m[2].metric("📋 Total tras aplicar", resumen_final["total_final"])

            previa_cmp = pd.DataFrame(tabla_final[1:], columns=tabla_final[0])

            categorias_cmp = sorted(c for c in previa_cmp.get("categoria", pd.Series(dtype=str)).unique() if c)
            if categorias_cmp:
                fcol1, fcol2 = st.columns([2, 1])
                elegidas = fcol1.multiselect(
                    "🗂️ Filtrar por categoría (lámparas, sillones, mesas…)",
                    categorias_cmp, default=[],
                    help="Útil cuando el tablero mezcla varias categorías, por ejemplo cuando estás "
                         "amueblando toda una casa a la vez.",
                )
                if elegidas:
                    previa_cmp = previa_cmp[previa_cmp["categoria"].isin(elegidas)]

            config_cmp = {
                "foto": st.column_config.ImageColumn("foto", width="small"),
                comparar.COL_MEJOR: st.column_config.TextColumn(comparar.COL_MEJOR, width="medium"),
                comparar.COL_DECISION: st.column_config.TextColumn(comparar.COL_DECISION, width="small"),
            }
            for columna in tabla_final[0]:
                if columna.startswith(f"liga{comparar.SEPARADOR}"):
                    config_cmp[columna] = st.column_config.LinkColumn(columna, display_text="abrir")
            st.dataframe(
                previa_cmp, use_container_width=True, height=380,
                column_order=[
                    "foto", "producto", "variante", "categoria",
                    comparar.COL_MEJOR, comparar.COL_DECISION,
                ] + [c for c in tabla_final[0] if c not in comparar.META],
                column_config=config_cmp,
            )
            st.caption(
                f"Mostrando {len(previa_cmp)} de {resumen_final['total_final']} producto(s) del tablero. "
                f"La columna **{comparar.COL_MEJOR}** se recalcula sola cada vez que agregas una tienda "
                "(el filtro de categoría solo afecta esta vista previa, no lo que se escribe en tu hoja)."
            )

            st.warning(
                "Al aplicar, la pestaña «Comparación» se reescribe completa con esta tabla. No se "
                "borran columnas de otras tiendas ni renglones que ya existían."
                + (" Antes de escribir guardo una copia en la pestaña «Respaldo»." if respaldar else
                   " **Tienes el respaldo apagado.**")
            )

            if st.button("Aplicar a mi tablero de comparación", type="primary"):
                try:
                    with st.spinner("Escribiendo tu tablero…"):
                        res = sheets.aplicar_comparacion(
                            contexto_cmp, tabla_final, nuevos=resumen_final["nuevos_finales"],
                            respaldar=respaldar, pestana=pestana,
                        )
                    st.toast("Tu tablero quedó actualizado.", icon="✅")
                    st.success(
                        f"Listo. «{plan_cmp.tienda}» quedó agregada a {resumen_final['total_final']} "
                        "producto(s) del tablero."
                    )
                    st.link_button("Abrir mi tablero", res["url"])
                    limpiar_resultados()
                except sheets.ErrorSheets as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"No pude escribir en tu tablero: {e}")

        # ─────────────────────────────────────────── modos simples
        elif modo in ("reemplazar", "nueva", "agregar"):
            st.subheader("Enviar a Google Sheets")
            st.caption(NOMBRES_MODO[modo] + ".")
            if st.button("Enviar a Google Sheets", type="primary"):
                try:
                    with st.spinner("Escribiendo en tu hoja…"):
                        res = sheets.escribir(
                            a_tabla(productos), destino=destino, pestana=pestana, modo=modo,
                            compartir_con=compartir, ruta_creds=ruta_creds,
                        )
                    st.toast("Tu hoja quedó escrita.", icon="✅")
                    st.success(f"Listo: {res['filas']} renglones en la pestaña «{res['pestana']}».")
                    st.link_button("Abrir la hoja", res["url"])
                    if res["creado"] and not compartir:
                        st.info(
                            "Creé una hoja nueva a nombre del robot. Escribe tu correo arriba y vuelve "
                            "a enviar para que también aparezca en tu Drive."
                        )
                except sheets.ErrorSheets as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"No pude escribir en Sheets: {e}")
