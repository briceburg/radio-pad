FROM python:3.13-alpine

RUN python3 -m venv /venv \
  && chown -R nobody:nobody /venv

ENV \
  PATH="/venv/bin:$PATH" \
  PYTHONPYCACHEPREFIX=/tmp/pycache

WORKDIR /app
USER nobody

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
