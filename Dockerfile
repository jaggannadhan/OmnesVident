# ─────────────────────────────────────────────────────────────────────────────
# OmnesVident — Production Dockerfile
# Target: Google Cloud Run (managed)
# Base:   python:3.12-slim  (small attack surface, no build tools bloat)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# Real-time log streaming to Cloud Logging
ENV PYTHONUNBUFFERED=1

# Cloud Run injects PORT=8080; default here matches that expectation
ENV PORT=8080

# Create a non-root user for the container process
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Install Python dependencies first (cached layer unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY api_storage/        api_storage/
COPY ingestion_engine/   ingestion_engine/
COPY intelligence_layer/ intelligence_layer/
COPY database/           database/
COPY tasks/              tasks/

# Owned by the non-root user
RUN chown -R app:app /app
USER app

# Expose the Cloud Run port (documentation; Cloud Run maps $PORT automatically)
EXPOSE 8080

# Gunicorn with UvicornWorker for production ASGI:
#   --workers 1       One worker is correct for Cloud Run (scale via instances)
#   --threads 8       Thread pool for concurrent sync handlers
#   --timeout 0       No request timeout — ingestion cycles can run > 30 s
#   --bind :$PORT     Listen on the port Cloud Run injects
CMD exec gunicorn api_storage.routes:app \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind :$PORT \
        --workers 1 \
        --threads 8 \
        --timeout 0 \
        --access-logfile - \
        --error-logfile -
