FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV SECRETS_FILE=/app/secrets.txt
ENV API_CREDENTIALS_FILE=/app/Cookie/api_credentials.json
ENV QQ_CREDENTIAL_DIR=/app/credentials
ENV NETEASE_API_URL=http://music-api:3000

WORKDIR /app/qq_api

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/Cookie /app/credentials

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
