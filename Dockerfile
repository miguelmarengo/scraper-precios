FROM python:3.11-slim

# Usuario sin privilegios: la ruta de credenciales por defecto
# (~/.config/scraper-precios/credenciales.json) queda en /home/appuser/.
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Navegador opcional para catálogos armados con JavaScript (casilla "🧪 Renderizar
# con navegador", en la barra lateral, bajo 🛡️ Seguridad). Gratis y de código
# abierto (Playwright + Chromium). Se instala aquí, en la imagen, para no
# depender de que el contenedor tenga internet cada vez que alguien lo use.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium && chmod -R a+rX /ms-playwright

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
ENV HOME=/home/appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true"]
