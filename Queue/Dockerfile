FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 큐 상태를 메모리에 저장하므로 워커는 반드시 1개
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
