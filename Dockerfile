# ============================================
# Stage 1: Build NBIS
# ============================================
FROM debian:bullseye as nbis-builder

ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && \
    apt-get install -y \
    wget \
    ca-certificates \
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    libpng-dev \
    libjpeg-dev \
    libtiff-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and build NBIS
WORKDIR /tmp
RUN wget https://github.com/lessandro/nbis/tarball/master -O nbis.tar.gz && \
    tar -xzf nbis.tar.gz && \
    mv lessandro-nbis-* nbis && \
    ls -la nbis/

# Build NBIS - setup.sh configures the build, then we build from source directory
WORKDIR /tmp/nbis
RUN mkdir -p /usr/local/nbis && \
    chmod +x setup.sh && \
    ./setup.sh /usr/local/nbis --without-X11 && \
    make && \
    make install

# Verify binaries were built and installed
RUN ls -la /usr/local/nbis/bin/ && \
    test -f /usr/local/nbis/bin/mindtct && echo "✅ mindtct built" || (echo "❌ mindtct FAILED" && find /usr/local/nbis -name mindtct && exit 1) && \
    test -f /usr/local/nbis/bin/bozorth3 && echo "✅ bozorth3 built" || (echo "❌ bozorth3 FAILED" && find /usr/local/nbis -name bozorth3 && exit 1) && \
    test -f /usr/local/nbis/bin/cwsq && echo "✅ cwsq built" || (echo "❌ cwsq FAILED" && find /usr/local/nbis -name cwsq && exit 1)

# ============================================
# Stage 2: Runtime image
# ============================================
FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/nbis/bin:${PATH}"

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpng16-16 \
    libjpeg62-turbo \
    libtiff5 \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Copy NBIS binaries and libraries from builder
COPY --from=nbis-builder /usr/local/nbis /usr/local/nbis

# Verify NBIS tools are present
RUN ls -la /usr/local/nbis/bin/ && \
    test -f /usr/local/nbis/bin/mindtct && echo "✅ mindtct copied" || exit 1 && \
    test -f /usr/local/nbis/bin/bozorth3 && echo "✅ bozorth3 copied" || exit 1 && \
    test -f /usr/local/nbis/bin/cwsq && echo "✅ cwsq copied" || exit 1

# Make all binaries executable
RUN chmod +x /usr/local/nbis/bin/*

# Test NBIS tools
RUN /usr/local/nbis/bin/mindtct 2>&1 | head -n 1 || true && \
    /usr/local/nbis/bin/bozorth3 2>&1 | head -n 1 || true && \
    echo "✅ NBIS tools verified"

# Set up application
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .

# Create temp directory
RUN mkdir -p /tmp/nbis_fingerprints && chmod 777 /tmp/nbis_fingerprints

EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:10000/health', timeout=5)" || exit 1

# Run application
CMD gunicorn app:app \
    --bind 0.0.0.0:${PORT:-10000} \
    --workers 2 \
    --timeout 120 \
    --worker-class sync \
    --log-level info \
    --access-logfile - \
    --error-logfile -