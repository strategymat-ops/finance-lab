# ============================================================================
# Finance Lab — Backend Dockerfile
# ============================================================================
# Production environment with institutional scientific and quantitative stack:
# Python 3.12, Rust (for high-speed core), QuantLib, PyTorch, Econ-ARK, Mesa
# ============================================================================

FROM python:3.12-slim-bookworm

# System dependencies for scientific computing, QuantLib compilation, and Rust
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    pkg-config \
    libssl-dev \
    libopenblas-dev \
    gfortran \
    rustc \
    cargo \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install dependencies in layers for fast caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . /app

# Port for FastAPI and WebSocket
EXPOSE 8000
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
