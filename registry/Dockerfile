FROM python:3.13-alpine

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV \
  PYTHONPATH=/app/src \
  REGISTRY_BIND_HOST=0.0.0.0 \
  REGISTRY_BIND_PORT=8000 \
  REGISTRY_LOG_LEVEL=info

CMD ["bin/docker/entrypoint.sh"]
