# =============================================================================
# Dockerfile for Kartik's Cloud-Native Flask App
# Build:  docker build -t kartik-flask-app:1.0 .
# Run:    docker run -d -p 5000:5000 --name kartik-flask-app kartik-flask-app:1.0
# =============================================================================

# ---- 1. Base image ----------------------------------------------------------
# Official, small Debian-based Python image (no compilers or extra tools).
FROM python:3.12-slim

# ---- 2. Image metadata (OCI labels) ----------------------------------------
LABEL org.opencontainers.image.title="kartik-flask-app" \
      org.opencontainers.image.description="Basic Python Flask app containerized with Docker and deployed on Kubernetes" \
      org.opencontainers.image.version="1.0" \
      org.opencontainers.image.authors="Kartik Saste" \
      org.opencontainers.image.licenses="MIT"

# ---- 3. Runtime environment -------------------------------------------------
# PYTHONDONTWRITEBYTECODE: don't write .pyc files into the image
# PYTHONUNBUFFERED:        send logs straight to stdout (visible in docker/kubectl logs)
# PIP_NO_CACHE_DIR:        keep the image small
# PIP_ROOT_USER_ACTION:    pip runs as root only at build time (app runs as appuser)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    APP_VERSION=1.0.0 \
    PORT=5000

WORKDIR /app

# ---- 4. Dependencies (cached layer) ----------------------------------------
# Copy ONLY requirements.txt first. Docker caches this layer, so dependencies
# are re-installed only when requirements.txt changes, not on every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- 5. Non-root user -------------------------------------------------------
# Running as root inside a container is a security risk, so create a
# dedicated unprivileged user.
RUN groupadd --gid 10001 appgroup \
 && useradd --uid 10001 --gid appgroup --no-create-home --shell /usr/sbin/nologin appuser

# ---- 6. Application code ----------------------------------------------------
COPY --chown=appuser:appgroup app.py .
COPY --chown=appuser:appgroup templates/ ./templates/

USER appuser

# ---- 7. Network port --------------------------------------------------------
# Documents the port gunicorn listens on (publish it with -p 5000:5000).
EXPOSE 5000

# ---- 8. Container health check ---------------------------------------------
# Docker marks the container healthy/unhealthy by calling /health.
# Uses Python's standard library because the slim image has no curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=4).status == 200 else 1)"

# ---- 9. Start command -------------------------------------------------------
# gunicorn is a production WSGI server; 2 workers, logs to stdout/stderr.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
