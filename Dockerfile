# Multi-stage build for Seestar INDI driver

# Stage 1: Development environment
FROM python:3.10-slim as dev

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    libindi-dev \
    astrometry.net \
    astrometry-data-tycho2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies for development
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional development dependencies
RUN pip install --no-cache-dir \
    black \
    isort \
    flake8 \
    pylint \
    mypy \
    pytest \
    pytest-cov

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV SEESTAR_CONFIG_DIR=/app/config
ENV SEESTAR_LOG_DIR=/app/logs

# Create necessary directories
RUN mkdir -p /app/config /app/logs /app/images

# Stage 2: Testing environment
FROM dev as test

# Run tests
CMD ["pytest", "--cov=.", "--cov-report=xml", "--cov-report=term-missing"]

# Stage 3: Production environment
FROM python:3.10-slim as prod

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libindi1 \
    astrometry.net \
    astrometry-data-tycho2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only necessary files
COPY --from=dev /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=dev /app/indi ./indi
COPY --from=dev /app/config ./config

# Create necessary directories
RUN mkdir -p /app/logs /app/images

# Set environment variables
ENV PYTHONPATH=/app
ENV SEESTAR_CONFIG_DIR=/app/config
ENV SEESTAR_LOG_DIR=/app/logs

EXPOSE 8080
EXPOSE 9090

# Start the application
CMD ["python", "-m", "indi.seestar_driver"]
