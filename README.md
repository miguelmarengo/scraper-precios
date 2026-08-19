# scraper-precios

Scraper mínimo de precios para Micaela.

## Uso

```bash
python scraper_micaela.py /ruta/al/archivo.html
python scraper_micaela.py https://ejemplo.com/productos
```

El comando imprime una lista JSON con pares `name` y `price`, reutilizando la etiqueta de texto visible más cercana cuando el precio aparece en un nodo separado.