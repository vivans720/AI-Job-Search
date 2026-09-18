FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOME=/home/appuser

WORKDIR /app

# Install system dependencies including curl, libpq, and tini for PID 1 signal management
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    git \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged user and browser directory with appropriate permissions
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /ms-playwright /app/data && \
    chown -R appuser:appuser /ms-playwright /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium & system deps
RUN playwright install --with-deps chromium && \
    chown -R appuser:appuser /ms-playwright

COPY . .

RUN chmod +x /app/entrypoint.sh && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

