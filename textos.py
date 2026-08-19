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
}

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
