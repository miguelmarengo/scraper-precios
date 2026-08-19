"""Interfaz web local. Se arranca con:  bash abrir.sh"""

from __future__ import annotations

import io
import os
import time
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

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

MODOS = ["sincronizar", "reemplazar", "nueva", "agregar"]
NOMBRES_MODO = {
    "sincronizar": "Actualizar mi hoja, respetando lo que ya tiene",
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
    for k in ("productos", "informe", "plan", "contexto"):
        st.session_state.pop(k, None)


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

    d1, d2 = st.columns([3, 1])
    destino = d1.text_input(
        "Tu hoja de Google",
        placeholder="https://docs.google.com/spreadsheets/d/…",
        help="Pega la URL completa de tu hoja. Si la dejas vacía (y no estás sincronizando), "
             "se crea una hoja nueva.",
    )
    pestana = d2.text_input("Pestaña", value="Productos", help="El nombre de la pestaña dentro de tu hoja.")

    estrategia = "auto"
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

    if modo != "sincronizar":
        compartir = st.text_input(
            "Si creo una hoja nueva, compártela con",
            placeholder="tucorreo@gmail.com",
            help="La hoja nace a nombre del robot. Escribe tu correo para que también llegue a tu Drive.",
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

        # ─────────────────────────────────────────── modos simples
        elif modo != "sincronizar":
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
