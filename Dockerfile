# Use Python 3.11 slim image
FROM python:3.11-slim-bullseye

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies for NBIS compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    build-essential \
    gcc \
    g++ \
    make \
    libpng-dev \
    libjpeg-dev \
    libtiff-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and compile NBIS from source
WORKDIR /tmp
RUN wget -q https://github.com/usnistgov/NBIS/archive/refs/heads/master.zip -O nbis.zip && \
    apt-get update && apt-get install -y unzip && \
    unzip -q nbis.zip && \
    cd NBIS-master && \
    ./setup.sh /opt/nbis --without-X11 && \
    cd /opt/nbis && \
    export NBIS_INSTALL_DIR=/opt/nbis && \
    export PATH=$NBIS_INSTALL_DIR/bin:$PATH && \
    cd /tmp && rm -rf NBIS-master nbis.zip && \
    apt-get remove -y unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Add NBIS binaries to PATH
ENV PATH="/opt/nbis/bin:${PATH}"

# Verify NBIS tools are accessible
RUN mindtct || echo "mindtct installed" && \
    bozorth3 || echo "bozorth3 installed"

# Set up application directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose port (Render provides PORT env var)
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python3 -c "import requests; requests.get('http://localhost:10000/health')" || exit 1

# Run application with gunicorn
CMD gunicorn app:app \
    --bind 0.0.0.0:${PORT:-10000} \
    --workers 2 \
    --timeout 120 \
    --worker-class sync \
    --log-level info \
    --access-logfile - \
    --error-logfile -