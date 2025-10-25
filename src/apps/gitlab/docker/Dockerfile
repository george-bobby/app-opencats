FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    requests \
    pyyaml \
    python-dotenv

# Create app user
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser ../core ./core
COPY --chown=appuser:appuser ../utils ./utils
COPY --chown=appuser:appuser ../config ./config
COPY --chown=appuser:appuser ../gitlab_github_import_full.py ./
COPY --chown=appuser:appuser ../README.md ./

# Copy Docker specific files
COPY --chown=appuser:appuser entrypoint.sh /app/
COPY --chown=appuser:appuser wait_for_gitlab.py /app/
COPY --chown=appuser:appuser import.conf /app/

# Make scripts executable
RUN chmod +x /app/entrypoint.sh && \
    chmod +x /app/wait_for_gitlab.py

# Switch to app user
USER appuser

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://gitlab:80', timeout=5)" || exit 1

# Default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python3", "gitlab_github_import_full.py"] 