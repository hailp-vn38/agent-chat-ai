# --------- Builder Stage ---------
FROM python:3.10-slim AS builder

# Install build dependencies for opuslib_next, sherpa-onnx, and other native packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopus-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements file for better layer caching
COPY requirements.txt .

# Create virtual environment and install dependencies
# Using --compile optimizes bytecode, improving startup time
RUN python -m venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /app/.venv/bin/pip install --no-cache-dir --compile -r requirements.txt

# --------- Final Stage ---------
FROM python:3.10-slim

# Install runtime dependencies (libopus for opuslib_next, libomp for torchaudio, ffmpeg for pydub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopus0 \
    libomp-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Create necessary directories with proper permissions
RUN mkdir -p /app/src/logs /app/tmp && \
    chown -R app:app /app

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy only necessary application code (exclude tests, docs, examples via .dockerignore)
COPY --chown=app:app src /app/src
COPY --chown=app:app run.py /app/

# Ensure the virtual environment is in the PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Switch to the non-root user
USER app

# Set the working directory to src for proper imports
WORKDIR /app/src


# Production alternative:
# CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production alternative:
# CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
