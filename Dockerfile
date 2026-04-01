FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tenant.py .
COPY scripts/ ./scripts/
COPY function-archive/ ./function-archive/
COPY executor-archive/ ./executor-archive/
COPY history/ ./history/
COPY database/ ./database/

ENV API_HOST=0.0.0.0
ENV API_PORT=5000

EXPOSE 5000

CMD ["python", "-u", "tenant.py"]
