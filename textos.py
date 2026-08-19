"""Todos los textos explicativos de la interfaz, juntos para poder ajustarlos
sin tocar la lógica."""

QUE_HACE = """
### En una frase

Le das la dirección de una tienda en línea, le dices qué te interesa, y te deja
una tabla ordenada en tu Google Sheet con precios, fotos, medidas e inventario.

### Los cuatro pasos

1. **¿De dónde?** — pegas la liga de la tienda. La app reconoce sola qué tecnología usa
   (Shopify, WooCommerce u otra) y elige la mejor forma de leer su catálogo.
2. **¿Qué quieres?** — escribes en español lo que buscas: *sillones blancos*, *verduras verdes*.
   Esto no solo recorta la lista: hace que el trabajo sea mucho más rápido, porque descarta
   los productos que no te interesan **antes** de abrir sus fichas.
3. **¿A dónde va?** — eliges si quieres actualizar una hoja que ya tienes (respetando lo que
   escribiste ahí) o empezar una desde cero.
4. **Revisas y aplicas** — antes de escribir nada te enseño exactamente qué va a cambiar.

### Lo que nunca hace

- No borra renglones tuyos.
- No borra columnas que tú hayas agregado.
- No escribe en tu hoja hasta que aprietas el botón de aplicar.
- Guarda una copia de lo que había en una pestaña de respaldo.
"""

AYUDA_FILTRO = """
Escribe con palabras normales lo que buscas. No importan los acentos, las mayúsculas,
el singular/plural ni el masculino/femenino: `sillones blancos` encuentra *Sillón blanca de lino*.

| Escribes | Trae |
|---|---|
| `sillones blancos` | lo que tenga **las dos** palabras |
| `sillon \\| sofa \\| loveseat` | **cualquiera** de las tres |
| `"sofá cama"` | esa **frase exacta** |
| `sillones -piel` | sillones, **excepto** los de piel |
| `verduras verdes -congelado` | se pueden combinar |

Se busca en el nombre, la marca, la categoría, el color, el material, las características
y la descripción del producto.

**Si lo dejas vacío**, trae el catálogo completo (hasta el máximo que pongas en los ajustes).
"""

AYUDA_MODOS = {
    "sincronizar": """
**Qué hace:** compara tu hoja con lo que acabo de encontrar y la actualiza renglón por renglón.

- Un producto que ya estaba y cambió de precio → **se actualiza** y te anoto qué cambió.
- Un producto que no estaba → **se agrega al final**.
- Un producto que estaba y hoy no apareció → **se queda tal cual**, marcado en rojo.
- Todo lo que tú hayas escrito en columnas propias (notas, proveedor, margen) **se respeta**.

**Cuándo usarlo:** es el modo de todos los días. Sirve para vigilar precios de la competencia
o tu propio catálogo a lo largo del tiempo.
""",
    "reemplazar": """
**Qué hace:** borra el contenido de la pestaña y escribe los resultados de cero.

**Cuándo usarlo:** la primera vez, o cuando quieres empezar limpio. **Ojo:** se pierde
lo que hubiera escrito ahí.
""",
    "nueva": """
**Qué hace:** crea una pestaña nueva con la fecha y hora en el nombre, sin tocar las que ya existen.

**Cuándo usarlo:** cuando quieres guardar fotografías de distintos momentos y compararlas después.
""",
    "agregar": """
**Qué hace:** pega los resultados al final de la pestaña, sin borrar nada.

**Cuándo usarlo:** para armar un historial largo de precios, una corrida debajo de la otra,
y luego graficarlo.
""",
    "comparar": """
**Qué hace:** en vez de un renglón por corrida, arma **un renglón por producto** y le va
agregando una **columna de precio por cada tienda** que revisas — con foto, liga directa y
el mejor precio ya calculado.

- Primera corrida (ej. *sillones blancos* en Palacio de Hierro) → crea el tablero.
- Segunda corrida (ej. los mismos sillones en Liverpool) → **agrega la columna** `precio · Liverpool`
  en el mismo renglón del producto, para poder comparar de un vistazo.
- Un producto que solo existe en una tienda → esa columna se queda vacía para las demás, sin
  problema.
- La columna **🏆 mejor precio** te dice, sin que tengas que leer columna por columna, cuál
  tienda tiene el precio más bajo *ahora mismo* para ese producto.
- La columna **decisión** trae un menú (👀 viendo · ⭐ favorito · 🛒 comprado) para que le des
  seguimiento a cada cosa que vas a comprar para tu casa.

**Cómo empareja "el mismo producto" entre tiendas distintas:** por nombre (y variante), no por
SKU ni por liga —cada tienda usa los suyos. Si el nombre es idéntico, se empareja solo. Si se
parece pero no es idéntico, te lo enseño para que confirmes antes de guardar nada.

**Cuándo usarlo:** para amueblar o remodelar comparando lo mismo entre varios lugares — lámparas,
sillones, mesas, focos, piso — en Palacio de Hierro, Liverpool, West Elm, Home Depot, etc. También
sirve para lo de todos los días: el mismo foco o la misma verdura en Walmart, Comercial Mexicana...
""",
}

AYUDA_COMPARAR = """
No hay SKU compartido entre tiendas, así que el emparejamiento se hace por el **nombre del
producto** (y su variante), normalizado igual que el buscador de la app: sin acentos, sin
mayúsculas, tolerando plural y género.

| Qué encuentra | Qué pasa |
|---|---|
| ✅ Nombre idéntico a uno que ya estaba | Se empareja solo — se agrega la columna de precio de esta tienda a ese renglón |
| 🤔 Nombre parecido, no idéntico | Te lo enseño para que **tú** confirmes si es el mismo producto |
| 🆕 No se parece a nada de lo que había | Se agrega como renglón nuevo |

Si dos productos son en realidad el mismo pero con nombres muy distintos entre tiendas (por
ejemplo "Sillón Oslo" vs "Sofá individual nórdico"), no se van a emparejar solos — quedan como
renglones separados y los puedes unir a mano en la hoja si quieres.

**Columnas que trae el tablero, sin que hagas nada:**

| Columna | Para qué sirve |
|---|---|
| `foto` | La miniatura del producto — nunca solo la liga, para que sepas qué estás viendo de un vistazo |
| `producto` · `variante` · `categoria` | Con qué se emparejó y en qué grupo cae (lámparas, sillones, mesas…) |
| `decisión` | Menú de 👀 viendo · ⭐ favorito · 🛒 comprado, para llevar el pendiente de tu proyecto |
| `🏆 mejor precio` | Se recalcula sola: la tienda más barata *ahora* para ese producto, resaltada en dorado en tu hoja |
| `precio` · `disponible` · `liga` · `actualizado` **por cada tienda** | El detalle completo, con liga directa para comprar |

**Ideas para cuando estás amueblando algo grande** (una casa, una remodelación): corre el
mismo tablero de comparación por categoría — un filtro de *lámparas de piso*, otro de
*sillones*, otro de *focos 20w* — así cada categoría queda en su propio grupo de renglones
dentro del mismo tablero, y la columna `categoria` te deja filtrar la hoja por cuarto o por tipo
de mueble sin perder la comparación de precios entre tiendas.
"""

LEYENDA = """
| Punto | Qué significa | Qué le pasa al renglón |
|---|---|---|
| 🟢 **nuevo** | No estaba en tu hoja | Se agrega al final |
| 🟡 **cambió** | Ya estaba y algún dato se movió | Se actualiza; en la columna `cambios` queda anotado qué |
| 🔴 **no encontrado** | Estaba en tu hoja pero hoy no apareció en la tienda | **No se toca.** Puede estar agotado, descontinuado, o el filtro ya no lo alcanza |
| ⚪ **sin cambios** | Ya estaba y todo sigue igual | Solo se le actualiza la fecha de revisión |

El color se pinta también como fondo del renglón en Google Sheets.

**Importante sobre el rojo:** no significa que el producto desapareció del mundo. Significa que
*esta corrida* no lo encontró. Si cambiaste el filtro entre una corrida y otra, van a salir en
rojo productos que simplemente ya no estás pidiendo.
"""

AYUDA_EMPAREJAMIENTO = """
Para saber si un producto de la tienda es "el mismo" que un renglón de tu hoja, hace falta
un identificador. Se usa este orden:

- **Automático** (recomendado): usa el **SKU** cuando el producto lo tiene. Si no, usa la
  **liga del producto** junto con la variante. Es lo que funciona en la mayoría de los casos.
- **Solo SKU**: útil si la tienda reacomoda sus ligas seguido y eso te está generando
  falsos «nuevos». Requiere que todos tus renglones tengan SKU.
- **Solo la liga**: útil si la tienda no publica SKU, o si repite el mismo SKU en productos
  distintos.

Los renglones de tu hoja que no tengan ni SKU ni liga no se pueden emparejar con nada,
así que siempre van a salir en rojo. La app te avisa cuántos son.
"""

AYUDA_COLUMNAS = """
| Columna | Qué trae |
|---|---|
| `estado` | El punto de color de esta corrida |
| `cambios` | Qué se movió respecto a la corrida anterior |
| `revisado_en` | Cuándo se revisó por última vez. En los rojos es la última vez que **sí** apareció |
| `foto` | La imagen incrustada en la celda |
| `nombre` · `variante` · `sku` · `marca` · `categoria` | Identificación del producto |
| `precio` · `precio_lista` · `descuento_pct` · `moneda` | Lo económico. `descuento_pct` se calcula |
| `disponible` · `inventario` | Si hay, y cuántas piezas (solo si la tienda lo publica) |
| `tiempo_entrega` | La promesa de entrega que aparece en la ficha |
| `color` · `material` · `garantia` | Detectados del texto o de los datos estructurados |
| `alto_cm` · `ancho_cm` · `largo_cm` · `profundidad_cm` · `diametro_cm` | Siempre en centímetros, vengan en pulgadas, milímetros o metros |
| `peso_kg` · `capacidad` | Peso siempre en kilos; capacidad en ml o litros |
| `dimensiones` | La medida combinada tal como la publica la tienda |
| `caracteristicas` · `descripcion` | El resto del texto del producto |
| `imagen` · `imagenes` | La liga de la foto principal y hasta 8 fotos |
| `url_producto` | Liga directa a la ficha, para comprobar cualquier dato |
| `plataforma` · `fecha_extraccion` | De dónde y cuándo salió |

Y cualquier columna que **tú** hayas agregado se conserva al final, intacta.
"""

AYUDA_LIMITES = """
Hay tres datos que dependen de que la tienda quiera publicarlos:

- **Inventario exacto.** Shopify y WooCommerce suelen darlo. La mayoría de las tiendas solo
  dice «disponible / agotado». Cuando no lo publican, la columna sale vacía.
- **Tiempo de entrega.** Se detecta cuando la tienda lo escribe en la ficha del producto o en
  su política de envíos. Si solo lo calcula en el carrito con tu código postal, no aparece.
- **Medidas.** Las más confiables vienen de datos estructurados. Cuando hay que leerlas del
  texto corrido de la ficha, puede colarse el dato de un producto sugerido en la misma página.
  Si un número te parece raro, la columna `url_producto` te lleva a comprobarlo.

Tampoco funciona bien en tiendas cuyo catálogo se arma con JavaScript (VTEX, Magento y algunas
hechas a medida): ahí puede salir muy poco o nada.
"""

AYUDA_GOOGLE = """
Para que la app pueda escribir en tus hojas, Google pide una **cuenta de servicio**: un
"robot" con su propio correo, al que tú le das permiso de editar una hoja específica.
Es gratis y se configura una sola vez.

Los pasos completos están en el **README**, sección *Google*. En resumen:

1. Creas un proyecto en Google Cloud y habilitas *Google Sheets API* y *Google Drive API*.
2. Creas una cuenta de servicio y descargas su llave en formato JSON.
3. Guardas ese archivo en la ruta que aparece aquí abajo.
4. Copias el correo del robot (aparecerá aquí) y compartes tu hoja con él **como Editor**.

Sin el paso 4 vas a ver un error de permisos: el robot existe pero tu hoja no lo conoce.
"""

AYUDA_AGENTE = """
El **agente de Micaela** es un asistente de IA opcional. Le describes un gusto, una persona o
un criterio — *"los que elegiría un arquitecto minimalista"*, *"los que usaría un electricista
experto"*, *"los que se ven más frescos"* — y en la pestaña **5️⃣ Resultados** te pone un
puntaje del 0 al 100 y una razón corta a cada producto que ya extrajiste.

**Qué puede hacer bien:** razonar con el texto que el scraper ya sacó — nombre, descripción,
material, características, precio — y compararlo contra el criterio que le diste, como lo
haría alguien con buen ojo y mucho tiempo libre.

**Qué no puede hacer:** no ve las fotos ni prueba productos. No sabe con certeza qué tan
madura está una fruta, qué pensaría exactamente una persona real, ni si un producto es bueno
en la vida real — solo puede leer lo que la tienda escribió. Cuando el texto no le alcanza para
decidir, se le pide que lo diga en la razón en vez de inventar. Es una opinión, no una garantía:
revisa tú antes de comprar.

**Qué necesita:** una llave de API de OpenAI (o de otro proveedor compatible, cambiando la
variable `AGENTE_BASE_URL`). Es tuya y el costo de cada consulta corre por tu cuenta — no la
pone esta app. Los textos de los productos que evalúes se envían al servidor de ese proveedor,
así que solo úsalo si te parece bien compartir esa información. Si no pones ninguna llave, el
resto de la app funciona igual; solo esta sección queda apagada.
"""
