FROM python:3.13-alpine

# TODO: use a backend w/o X/Wayland reqs
RUN apk add --no-cache mpv

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "src/radio-pad.py"]