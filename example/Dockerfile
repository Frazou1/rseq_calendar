FROM python:3.11-slim

# --- Optimisations Python ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- Timezone (pour éviter les surprises de décalage) ---
ENV TZ=America/Toronto
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# --- Dépendances système pour Chromium/Selenium ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libgtk2.0-0 \
    libgbm-dev \
    libasound2 \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Variables d'environnement utiles à Selenium/Chromium ---
ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER=/usr/bin/chromedriver \
    CHROMIUM_FLAGS="--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu --window-size=1920,1080"

# --- Dépendances Python ---
RUN pip install --no-cache-dir \
    "selenium==4.*" \
    "webdriver-manager==4.*" \
    "beautifulsoup4>=4.12,<5" \
    "paho-mqtt==1.6.1" \
    "requests>=2.31,<3"

# --- Répertoire de travail ---
WORKDIR /app

# --- Copie des fichiers de l’add-on ---
COPY run.sh /run.sh
COPY script.py /script.py
RUN chmod a+x /run.sh

# Si tu veux, tu peux ajouter un HEALTHCHECK plus tard (exige curl/wget)
# HEALTHCHECK --interval=1m --timeout=5s CMD python /app/healthcheck.py || exit 1

CMD [ "/run.sh" ]
