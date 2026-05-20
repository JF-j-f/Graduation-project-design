FROM maven:3.9.9-eclipse-temurin-23

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

WORKDIR /opt/musicweb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-mysql-server \
        redis-server \
        nodejs \
        npm \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        supervisor \
        build-essential \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY Project/MusicWeb ./Project/MusicWeb
COPY Project/MusicMode ./Project/MusicMode
COPY docker/dist/release-data/musicweb.sql ./data/musicweb.sql
COPY docker/dist/release-data/Mode ./Project/MusicMode/Mode
COPY docker/release/runtime/validate_and_generate_config.py ./runtime/validate_and_generate_config.py
COPY docker/release/all-in-one/supervisord.conf /etc/supervisor/conf.d/musicweb.conf
COPY docker/release/all-in-one/entrypoint.sh ./runtime/entrypoint.sh

RUN chmod +x ./runtime/entrypoint.sh \
    && cd Project/MusicWeb && mvn -DskipTests package \
    && cd /opt/musicweb/Project/MusicWeb/src/main/webapp/MusicServer && npm ci --omit=dev \
    && cd /opt/musicweb/Project/MusicWeb/src/main/webapp/MusicServer/unblock && npm install --omit=dev \
    && python3 -m venv /opt/musicweb/venv-qq \
    && /opt/musicweb/venv-qq/bin/pip install --no-cache-dir -r /opt/musicweb/Project/MusicWeb/src/main/webapp/MusicServer/qq_api/requirements.txt \
    && python3 -m venv /opt/musicweb/venv-recommender \
    && /opt/musicweb/venv-recommender/bin/pip install --no-cache-dir -r /opt/musicweb/Project/MusicMode/scripts/requirements_server.txt \
    && /opt/musicweb/venv-recommender/bin/pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0

EXPOSE 8082 3000 8000 8081

ENTRYPOINT ["/opt/musicweb/runtime/entrypoint.sh"]
