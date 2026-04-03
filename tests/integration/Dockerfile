FROM python:3.13-alpine

WORKDIR /tests
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER nobody
CMD ["pytest", "-v", "--tb=short", "-p", "no:cacheprovider"]
