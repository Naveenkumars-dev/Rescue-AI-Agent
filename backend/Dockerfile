# RescueFlow AI backend container.
# Uses the official decider_kit (bundled at repo root) and Strands Decider 2B integration.
FROM python:3.13-slim

WORKDIR /app

# System deps for building some Python wheels if needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better layer caching.
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the official hackathon kit and the application.
COPY decider_kit /app/decider_kit
COPY backend/app /app/app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check hits the FastAPI /health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
