FROM python:3.12-slim

WORKDIR /payload

COPY musicweb.sql /payload/sql/musicweb.sql
COPY Mode /payload/models/Mode
COPY validate_and_generate_config.py /opt/musicweb/validate_and_generate_config.py

CMD ["python", "/opt/musicweb/validate_and_generate_config.py"]
