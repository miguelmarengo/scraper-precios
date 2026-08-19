# Scraper de precios → Google Sheets

Aplicación local y gratuita. Le pegas la URL de una tienda en línea, le dices qué te interesa
(«sillones blancos», «verduras verdes») y te deja en tu Google Sheet una tabla con fotos,
precios, descuentos, medidas, peso, inventario y tiempo de entrega.

Puede **actualizar una hoja que ya tienes**, renglón por renglón, marcando con un punto de color
qué es nuevo 🟢, qué cambió 🟡 y qué ya no encontró 🔴, sin borrar nada de lo que tú escribiste.

Todo corre en tu Mac. No hay servidor, no hay suscripción, no hay límite de uso.

---

## 1. Instalación (una sola vez)

Abre la app **Terminal**, entra a la carpeta del proyecto y corre:

```bash
bash instalar.sh
```

Eso crea un entorno aislado (`.venv`) e instala las librerías. Tarda un par de minutos.

## 2. Abrir la aplicación

```bash
bash abrir.sh
```

Se abre el navegador en `http://localhost:8501`. La página está organizada en cuatro pasos
numerados y cada control trae su explicación. Para cerrarla, `Ctrl+C` en la Terminal.

Sobre los resultados puedes **buscar** (por nombre, SKU, color, marca…) y **ordenar** por mayor
descuento o por precio, sin volver a extraer nada. Si la tienda tiene ofertas, arriba de la
tabla aparece un panel con las **🔥 mejores ofertas** de esa corrida.

---

## 3. Google: conectar tu hoja

Se usa una **cuenta de servicio**: un "robot" de Google al que le das permiso de editar tus hojas.
Es gratis y se configura una sola vez (≈10 minutos).

1. Entra a <https://console.cloud.google.com/> con tu cuenta de Google.
2. Arriba a la izquierda, **crea un proyecto nuevo** (nómbralo por ejemplo `scraper-precios`).
3. Activa las dos APIs que hacen falta. Búscalas en el buscador de arriba y dale **Habilitar** a cada una:
   - **Google Sheets API**
   - **Google Drive API**
4. Ve a **APIs y servicios → Credenciales → Crear credenciales → Cuenta de servicio**.
   Ponle un nombre, dale **Crear y continuar** y luego **Listo** (puedes saltarte los pasos de roles).
5. Entra a la cuenta de servicio recién creada → pestaña **Claves** → **Agregar clave → Crear clave nueva → JSON**.
   Se descarga un archivo `.json`.
6. Mueve y renombra ese archivo:

   ```bash
   mkdir -p ~/.config/scraper-precios
   mv ~/Downloads/EL-ARCHIVO-QUE-BAJASTE.json ~/.config/scraper-precios/credenciales.json
   ```

7. Abre la aplicación. En la barra lateral aparecerá un correo tipo
   `algo@tu-proyecto.iam.gserviceaccount.com`. **Cópialo.**
8. Abre tu Google Sheet → botón **Compartir** → pega ese correo → dale permiso de **Editor**.

Ya está. Pega la URL de tu hoja en el **paso 3** de la página.

> El paso 8 es el que más se olvida: sin compartir la hoja con el correo del robot, verás un
> error de permisos. El robot existe, pero tu hoja no lo conoce.

> Si dejas el campo de la hoja vacío (y **no** estás sincronizando), la aplicación crea una hoja
> nueva. En ese caso escribe tu correo en "compártela con" para que aparezca en tu Drive; si no,
> quedará únicamente a nombre del robot.

---

## 4. Actualizar una hoja que ya tienes (el modo del día a día)

Este es el modo importante. En el paso 3 de la página eliges **«Actualizar mi hoja, respetando
lo que ya tiene»**, pegas la URL de tu hoja, y la app compara renglón por renglón.

### Qué verás en tu hoja

Se agregan tres columnas al principio:

| Columna | Qué trae |
|---|---|
| `estado` | El punto de color de esta corrida |
| `cambios` | `precio: 200.00 → 180.00; inventario: 2 → 0` |
| `revisado_en` | Cuándo se revisó. En los rojos, la última vez que **sí** apareció |

Y cada renglón queda marcado, con el mismo color de fondo:

| Punto | Qué significa | Qué le pasa al renglón |
|---|---|---|
| 🟢 **nuevo** | No estaba en tu hoja | Se agrega al final |
| 🟡 **cambió** | Ya estaba y algún dato se movió | Se actualiza, y en `cambios` queda anotado qué |
| 🔴 **no encontrado** | Estaba, pero hoy no apareció en la tienda | **No se toca nada de ese renglón** |
| ⚪ **sin cambios** | Ya estaba y sigue igual | Solo se actualiza la fecha |

Se vigilan estos campos para decidir si algo "cambió": precio, precio de lista, descuento,
disponibilidad, inventario y tiempo de entrega. El resto se actualiza en silencio.

### Cómo sabe que un producto es "el mismo" de antes

Necesita un identificador. El modo **automático** usa el **SKU** cuando el producto lo tiene, y
si no, la **liga del producto** junto con la variante. Puedes forzar uno u otro desde la página.

Detalles que ya están resueltos:

- `1299` y `1299.00` se consideran el mismo precio; no generan un falso 🟡.
- Las ligas se comparan sin la diagonal final y sin parámetros de rastreo (`?utm_source=…`).
- Los renglones de tu hoja sin SKU ni liga no se pueden emparejar: siempre saldrán en 🔴, y la
  app te dice cuántos son.
- Si tu hoja tiene el mismo SKU repetido, se empareja el primero y se te avisa.

### Lo que se respeta

- **Tus columnas.** Si agregaste `notas`, `proveedor` o `margen`, se conservan con su contenido.
  En los renglones nuevos quedan vacías, listas para que las llenes.
- **Tus renglones.** Nunca se borra ninguno, ni siquiera los 🔴.
- **Tus fotos.** La hoja se lee pidiendo las *fórmulas*, no su resultado; por eso las celdas con
  `=IMAGE(...)` sobreviven a la reescritura.

### Lo que sí cambia, y conviene saber

Al aplicar, **la pestaña se reescribe completa**. El contenido se conserva, pero las columnas
se reordenan: primero las tres de control, luego las de datos, y al final las tuyas. Si tienes
fórmulas en otras pestañas que apuntan a celdas concretas de esta (`Productos!F12`), revísalas
después. Antes de escribir se guarda una copia de lo anterior en la pestaña
**«Respaldo (antes de sincronizar)»**.

### Una advertencia sobre el rojo

🔴 no quiere decir "el producto ya no existe". Quiere decir "esta corrida no lo encontró". Si
cambiaste el filtro entre una corrida y otra, van a salir en rojo productos que simplemente ya
no estás pidiendo. Para vigilar precios en el tiempo, **usa siempre el mismo filtro**.

---

## 5. El filtro: pedir solo lo que te interesa

En el campo **¿Qué quieres de esa página?** escribes en lenguaje normal:

| Escribes | Trae |
|---|---|
| `sillones blancos` | lo que tenga las dos palabras |
| `sillon \| sofa \| loveseat` | cualquiera de las tres |
| `"sofá cama"` | esa frase exacta |
| `sillones -piel` | sillones, pero sin los de piel |
| `verduras verdes -congelado` | se pueden combinar |

No importan los acentos, las mayúsculas, el singular/plural ni el masculino/femenino:
`sillones blancos` encuentra *Sillón blanca de lino*. Se busca en el nombre, la marca, la
categoría, el color, el material, las características y la descripción.

Debajo hay además **precio mínimo**, **precio máximo** y **solo disponibles**.

> **Por qué importa:** el filtro se aplica *antes* de abrir cada ficha. En una tienda de 4,000
> productos, pedir "sillones blancos" hace unas 20 peticiones en vez de 4,000. Es la diferencia
> entre 30 segundos y dos horas.

Si el filtro no encuentra nada, prueba con menos palabras (solo `sillon`) o quítalo para ver
primero qué trae el catálogo completo.

---

## 6. Qué columnas devuelve

| Columna | Contenido |
|---|---|
| `foto` | La imagen **incrustada** en la celda (fórmula `IMAGE()`) |
| `nombre` | Nombre del producto |
| `variante` | Talla / color / presentación |
| `sku` | Código del producto |
| `marca` | Fabricante o vendor |
| `categoria` | Categoría o tipo |
| `precio` | Precio actual, como número plano |
| `precio_lista` | Precio antes del descuento |
| `descuento_pct` | Porcentaje de descuento, calculado |
| `moneda` | MXN, USD, … |
| `disponible` | Sí / No / Preventa |
| `inventario` | Piezas en existencia, cuando la tienda lo publica |
| `tiempo_entrega` | Promesa de entrega detectada en la ficha |
| `color` | Color detectado |
| `material` | Material detectado |
| `alto_cm` `ancho_cm` `largo_cm` | Medidas, siempre convertidas a centímetros |
| `profundidad_cm` `diametro_cm` | Fondo y diámetro, en centímetros |
| `peso_kg` | Peso, siempre convertido a kilogramos |
| `capacidad` | Volumen (ml o L) para termos, botellas, tanques… |
| `dimensiones` | La medida combinada tal cual: `75 x 80 x 90 cm` |
| `garantia` | `2 años`, `6 meses`… |
| `caracteristicas` | Los demás atributos publicados |
| `descripcion` | Descripción, sin etiquetas HTML |
| `imagen` | URL de la foto principal |
| `imagenes` | Hasta 8 URLs de fotos, separadas por coma |
| `url_producto` | Liga directa a la ficha |
| `plataforma` | Shopify, WooCommerce, VTEX, Genérico… |
| `fecha_extraccion` | Cuándo se sacó el dato |

**Sobre las medidas:** se leen de tres fuentes, en este orden: los campos estructurados de
schema.org (`height`, `width`, `weight`), el peso que declara la variante en Shopify, y el texto
de la descripción (`Medidas: 75 x 80 x 90 cm`, `Altura 1.2 m`, `Pesa 3.5 kg`). Pulgadas,
milímetros, metros, gramos y libras se convierten solos a cm y kg. Cuando una medida sale del
texto corrido de la ficha, puede colarse el dato de un producto sugerido en la misma página;
si un valor te parece raro, la columna `url_producto` te lleva a comprobarlo.

**Sobre las fotos:** la columna `foto` trae `=IMAGE("...")`, así que en Google Sheets ves la
miniatura dentro de la celda (la app ensancha la columna y sube el alto de las filas sola).
En el CSV y el Excel esa columna sale como fórmula; si prefieres solo la liga, usa `imagen`.

---

## 7. Qué tan bien funciona según la tienda

| Plataforma | Qué tan completo sale |
|---|---|
| **Shopify** | Excelente. Usa el JSON público: todas las variantes, precios, SKU e inventario exacto. |
| **WooCommerce** | Muy bueno. Usa la Store API: precios, stock y atributos. |
| **Cualquier tienda con datos schema.org** | Bueno. Lee el JSON-LD que casi todas publican para aparecer en Google Shopping. |
| **VTEX / Magento / catálogos armados con JavaScript** | Variable sin ayuda extra — activa **🧪 Renderizar con navegador** (ver abajo). |

El **inventario exacto** es el dato más difícil: muchas tiendas solo publican "disponible / agotado"
y nunca el número de piezas. Cuando no lo publican, la columna sale vacía. Lo mismo con el tiempo de
entrega: se detecta cuando la tienda lo escribe en la ficha o en su política de envíos.

### Catálogos armados con JavaScript (React, Vue, Angular)

Algunas tiendas no ponen los datos del producto en el HTML que llega por internet: los arma un
programa en el propio navegador (JavaScript), después de cargar la página. Ahí una petición normal
solo ve una página casi vacía.

Para esos casos, en la barra lateral (**🛡️ Seguridad**) hay una casilla: **🧪 Renderizar con
navegador si el catálogo usa JavaScript**. Al activarla, la app abre esas páginas con un navegador
real y de código abierto (Chromium, vía [Playwright](https://playwright.dev)) y deja que corra su
propio JavaScript — exactamente lo mismo que le pasa a cualquier persona que visita la página. Es
más lento, así que solo actívala si de verdad la necesitas.

La primera vez, instala el navegador (una sola vez, gratis, ~180 MB):

```bash
.venv/bin/playwright install chromium
```

(Si usas Docker, ya viene instalado en la imagen — ver la sección 13.)

**Lo que esto no hace:** no evade `robots.txt` (sigue las mismas reglas que el resto de la app), no
inicia sesión por ti si el sitio exige login, y no resuelve CAPTCHAs ni burla sistemas anti-bot
como Cloudflare. Eso son controles de acceso deliberados del sitio; esta herramienta solo ve lo que
cualquier visitante normal vería.

---

## 8. Uso desde la terminal (para automatizar)

```bash
# guardar un CSV
./.venv/bin/python cli.py https://tienda.com --csv precios.csv

# solo lo que te interesa
./.venv/bin/python cli.py https://tienda.com --filtro "sillones blancos" --csv sillones.csv

# con rango de precio y solo lo que hay en existencia
./.venv/bin/python cli.py https://tienda.com --filtro "sofa | loveseat -piel" \
    --precio-max 20000 --solo-disponibles --csv sofas.csv

# escribir en una hoja existente
./.venv/bin/python cli.py https://tienda.com --sheet "https://docs.google.com/spreadsheets/d/XXXX"

# ir acumulando historial de precios (una corrida = filas nuevas)
./.venv/bin/python cli.py https://tienda.com --sheet "https://..." --modo agregar

# ACTUALIZAR tu hoja respetando lo que ya tiene (el modo del día a día)
./.venv/bin/python cli.py https://tienda.com --filtro "sillones blancos" \
    --sheet "https://docs.google.com/spreadsheets/d/XXXX" --modo sincronizar

# forzar el emparejamiento por SKU, sin guardar respaldo
./.venv/bin/python cli.py https://tienda.com --sheet "https://..." \
    --modo sincronizar --emparejar sku --sin-respaldo
```

Para vigilar precios todos los días, `--modo sincronizar` con el **mismo filtro** es lo que
quieres: tu hoja se va actualizando sola y los puntos de color te dicen qué se movió.

Para correrlo solo todos los días a las 8 a.m., agrégalo a `crontab -e`:

```
0 8 * * * cd /ruta/a/scraper-precios && ./.venv/bin/python cli.py https://tienda.com --sheet "https://..." --modo agregar
```

---

## 9. Ajustes de la barra lateral

Para no obligarte a entender ocho controles antes de tu primera corrida, la velocidad se elige
con un selector de tres sabores:

| Preset | Qué hace |
|---|---|
| ⚡ **Rápido** | Hasta 100 productos, sin abrir cada ficha (sin inventario ni medidas exactas). Para explorar una tienda por primera vez. |
| ⚖️ **Equilibrado** *(por defecto)* | Hasta 300 productos con inventario, medidas y tiempo de entrega. El punto medio para el uso diario. |
| 🔍 **Completo** | Hasta 1500 productos con todo el detalle. Tarda más, pero no se te escapa nada. |
| 🎛️ **Personalizado** | Te devuelve el control fino de siempre: |

Con **Personalizado** aparecen estos controles, uno por uno:

- **Máximo de resultados** — corta el catálogo. Empieza con 50 para probar.
- **Abrir cada ficha** — necesario para inventario, tiempo de entrega y medidas, pero multiplica
  el tiempo. Desactívalo si solo te interesan nombres y precios.
- **Pausa entre peticiones** — súbela si la tienda empieza a rechazar peticiones (error 429).
- **Peticiones en paralelo** — bájala a 1 o 2 si la tienda es sensible.
- **Pre-filtrar por la URL** — con un filtro activo, descarta de entrada las fichas cuya dirección
  no menciona ninguna de tus palabras. Acelera muchísimo. Si la tienda usa URLs con puros números
  (`/p/48211`), la app lo detecta y no lo aplica. Apágalo si sospechas que se está saltando productos.

Por separado, siempre visibles bajo "🛡️ Seguridad":

- **Respetar robots.txt** — déjalo encendido.
- **🧪 Renderizar con navegador si el catálogo usa JavaScript** — apagado por defecto (es más
  lento). Actívalo cuando una tienda te dé 0 productos y sospeches que arma su catálogo con
  React/Vue/Angular. Ver la sección 7 para el detalle de qué hace y qué no.
- **Guardar respaldo antes de sincronizar** — copia el contenido anterior a una pestaña
  «Respaldo» antes de reescribir la tuya.

---

## 10. Agente de Micaela (opcional): pídele una opinión con IA

Además de filtrar por palabras exactas, en la pestaña **5️⃣ Resultados** hay una caja que dice
*"Pregúntale al agente de Micaela"*. Ahí puedes escribir un gusto, una persona o un criterio en
lenguaje natural — por ejemplo:

- *"Los que elegiría un arquitecto minimalista, con concreto y líneas limpias"*
- *"Los que usaría un electricista que prioriza eficiencia y garantía"*
- *"Los que se ven más frescos y de mejor calidad"*

El agente le pone un puntaje del 0 al 100 y una razón corta, en español, a cada producto que
ya extrajiste — sin volver a tocar la tienda.

**Cómo activarlo:** en la barra lateral, sección "🤖 Agente de Micaela", pega una llave de API
de [OpenAI](https://platform.openai.com/api-keys) (empieza con `sk-`). Es tuya, el costo de cada
consulta corre por tu cuenta (usa un modelo económico por defecto), y solo vive en esa sesión del
navegador — no se guarda en ningún archivo. Si prefieres dejarla fija, define la variable de
entorno `OPENAI_API_KEY` (o `openai_api_key` en `st.secrets`) antes de abrir la app, igual que
`APP_PASSWORD`. Sin ninguna llave configurada, el resto de la app funciona exactamente igual;
solo esta caja queda apagada.

**Sus límites, para no llevarte una sorpresa:** el agente no ve fotos ni prueba productos —
razona únicamente sobre el texto que el scraper ya extrajo (nombre, descripción, material,
características, precio). No sabe con certeza qué pensaría una persona real, ni puede confirmar
qué tan fresca está una fruta con solo leer su ficha; cuando el texto no le alcanza para decidir,
se le pide que lo diga en la razón en vez de inventar. Es una opinión generada por IA, no una
garantía — revisa tú antes de comprar, sobre todo en productos perecederos.

Por defecto usa `gpt-4o-mini` contra la API de OpenAI, pero puedes apuntarlo a cualquier servicio
compatible (Groq, Together, un modelo local con Ollama, etc.) con las variables de entorno
`AGENTE_MODELO` y `AGENTE_BASE_URL`.

---

## 11. Pruebas

```bash
bash probar.sh
```

Levanta tiendas Shopify, WooCommerce y genérica simuladas en tu propia máquina y corre las
verificaciones de conversión de unidades, formatos de precio mexicanos y europeos, plurales y
género en el filtro, variantes, descuentos, fotos, inventario, toda la lógica de sincronización
(emparejamiento, altas, cambios, desaparecidos, columnas propias, respaldo y colores), y el
agente de IA (con un doble que simula sus respuestas). No toca internet ni Google ni OpenAI: todo
se verifica contra dobles que registran cada llamada.

---

## 12. Publicarla en internet

**Esta app ya no se publica en Streamlit Community Cloud.** Ahora corre en privado con Docker
(sección 13) — es la forma recomendada, y la que se usa hoy.

> **Sobre Vercel:** esta app es una interfaz de Streamlit, es decir, necesita un servidor
> Python corriendo todo el tiempo (con WebSocket para que los controles respondan). Vercel está
> pensado para páginas estáticas y funciones "sin estado" que responden una petición y terminan
> — no para procesos largos como este, y **no ejecuta contenedores Docker** como el de este
> proyecto. Por eso `docker compose up` (sección 12) no se puede simplemente "subir a Vercel":
> ahí no correría. Si en algún momento quieres una URL pública (no solo local o en tu red),
> lo que sí funciona con este mismo `Dockerfile` sin cambiarle nada es un servicio que sí
> corre contenedores: [Render](https://render.com), [Railway](https://railway.app),
> [Fly.io](https://fly.io) o Google Cloud Run. Todos tienen plan gratuito o muy barato para
> uso personal. Si prefieres quedarte 100% privada, Tailscale o un Cloudflare Tunnel
> (sección 13) evitan tener que subirla a ningún lado.

---

## 13. Correrla en privado con Docker

Si prefieres no depender de la URL pública de Streamlit Community Cloud —por ejemplo porque
es una herramienta de uso interno y no quieres que quede accesible a cualquiera con el
enlace— puedes correrla en tu propia máquina o servidor con Docker. Así nunca toca internet
salvo que tú decidas exponerla.

### Construir y correr

```bash
docker compose up --build
```

Se abre en `http://localhost:8501`. Para pararla: `Ctrl+C`, y `docker compose down` si quieres
liberar el contenedor por completo.

Si no usas `docker compose`, con Docker a secas:

```bash
docker build -t scraper-precios .
docker run -p 8501:8501 --env APP_PASSWORD=tu-clave scraper-precios
```

### Protegerla con contraseña

Sin nada configurado, cualquiera que llegue a la URL puede usarla. Para que pida una
contraseña antes de mostrar cualquier cosa, define la variable `APP_PASSWORD`:

```bash
APP_PASSWORD=tu-clave docker compose up --build
```

o edita el `docker-compose.yml` y pon la clave directamente en la línea de `environment`.
Esta misma variable funciona igual si corres la app con `bash abrir.sh` en tu computadora
(`export APP_PASSWORD=tu-clave` antes de abrirla). En Streamlit Community Cloud, el
equivalente es agregar `APP_PASSWORD = "tu-clave"` en **Settings → Secrets**.

### Dejar fija la llave del agente de IA (opcional)

Si no quieres pegar la llave de OpenAI cada vez que abres la app (ver sección 10), defínela
igual que `APP_PASSWORD`:

```bash
APP_PASSWORD=tu-clave OPENAI_API_KEY=sk-tu-llave docker compose up --build
```

### Conectar Google Sheets dentro del contenedor

El archivo `docker-compose.yml` ya trae preparada la línea que monta tu `credenciales.json`
en la ruta que la app espera. Descomenta/ajusta esa línea de `volumes` y coloca el archivo
junto al `docker-compose.yml` con ese nombre. Si solo vas a extraer y descargar en CSV/Excel,
puedes saltarte esto por completo.

### Si quieres acceder desde fuera de tu red

Docker por sí solo no la hace "privada" en internet — solo evita que quede en la URL pública
de Streamlit Cloud. Si necesitas que alguien más la use desde otro lugar, sin abrir puertos
en tu router, algo como [Tailscale](https://tailscale.com) o un
[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
te da una liga privada solo para los dispositivos que tú autorices. Con la contraseña de la
sección anterior de todos modos queda protegida aunque alguien más llegue a la liga.

---

## 14. Notas legales

Extraer datos públicos de precios es una práctica común, pero conviene tener en cuenta que:

- Muchos sitios lo prohíben en sus **términos de uso**, aunque el contenido sea público.
- El `robots.txt` indica qué rutas pide el sitio que no se rastreen; la app lo respeta por defecto.
- No se extraen datos personales ni contenido detrás de un login.
- Mantén la pausa entre peticiones para no afectar el servicio del sitio.

Revisa los términos del sitio que vayas a consultar, sobre todo si el uso es comercial.
