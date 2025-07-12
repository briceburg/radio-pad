FROM python:3.13-alpine

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV SWITCHBOARD_HOST=0.0.0.0
CMD ["python", "src/switchboard.py"]