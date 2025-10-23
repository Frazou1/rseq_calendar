FROM python:3.11-slim

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
    && rm -rf /var/lib/apt/lists/*

# Installer les packages Python nécessaires (ajout de "requests")
RUN pip install --no-cache-dir selenium==4.* webdriver-manager==4.* beautifulsoup4 paho-mqtt==1.6.1 requests

COPY run.sh /run.sh
COPY script.py /script.py

RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
