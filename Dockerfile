FROM python:3.12-slim

# Install PostgreSQL client library
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy source and install
COPY . .
RUN pip install --no-cache-dir .

# Remove build-only deps
RUN apt-get purge -y --auto-remove gcc

# Run as non-root user
RUN useradd -r -s /usr/sbin/nologin sentinel
USER sentinel

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "sentinel.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
