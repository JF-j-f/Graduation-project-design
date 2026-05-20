FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

WORKDIR /app/MusicMode

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY scripts/requirements_server.txt /tmp/requirements_server.txt
RUN pip install --no-cache-dir -r /tmp/requirements_server.txt \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0

COPY . .

CMD ["tail", "-f", "/dev/null"]
