FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# ติดตั้ง dependencies สำหรับระบบ (ถ้ามี ML บางตัวต้องใช้)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --reload for dev mode
CMD ["python", "-m", "uvicorn", "main_app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]