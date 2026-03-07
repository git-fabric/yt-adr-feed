# yt-adr-feed: Multi-stage Docker build
# Base: python:3.11-slim | Final image ~500MB (includes sentence-transformers model)
# Immutable tags only — no :latest in production (per ADR-003)

# === Builder stage ===
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency spec first (Docker layer caching)
COPY pyproject.toml ./

# Install Python packages
RUN pip install --no-cache-dir --prefix=/install .

# Copy source and install package
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install .

# === Runtime stage ===
FROM python:3.11-slim

WORKDIR /app

# Runtime dependencies: git for PR workflow
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy config as default
COPY config/ /app/config/

# Non-root user (security: least privilege per ADR-003 §6)
RUN groupadd -r ytadr && useradd -r -g ytadr -m ytadr
USER ytadr

# Pre-download embedding model at build time (deterministic, cached in image)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

ENTRYPOINT ["python", "-m", "yt_adr_feed"]
CMD ["--help"]
