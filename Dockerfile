# ========================================
# Stage 1: Build Frontend (cached aggressively)
# ========================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Install pnpm (cached layer)
RUN npm install -g pnpm@latest

# Copy only lock files first - this layer is cached until dependencies change
COPY h3xassist-web/package.json h3xassist-web/pnpm-lock.yaml ./

# Install dependencies (cached until pnpm-lock.yaml changes)
RUN pnpm install --frozen-lockfile

# Copy source and build (only re-runs when source changes)
COPY h3xassist-web/ ./
RUN pnpm build

# ========================================
# Stage 2: Python Runtime
# ========================================
FROM python:3.12-slim-bookworm AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PULSE_SERVER=unix:/run/pulse/native \
    XDG_RUNTIME_DIR=/run/user/0 \
    H3XASSIST_CONFIG_DIR=/root/.config/h3xassist \
    H3XASSIST_DATA_DIR=/root/.local/share/h3xassist \
    DISPLAY=:99

# Install system dependencies in a single layer with no bloat
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Audio
    ffmpeg \
    pipewire \
    pipewire-bin \
    pipewire-pulse \
    libpipewire-0.3-0 \
    pulseaudio-utils \
    # Chromium
    chromium \
    chromium-common \
    chromium-driver \
    # Headless Display
    xvfb xauth \
    # Chromium runtime libs (deduplicated)
    libnss3 libnspr4 \
    libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 \
    libcups2 libdrm2 libgbm1 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libpango-1.0-0 libcairo2 \
    libgtk-3-0 libx11-xcb1 libxcb1 libxcursor1 libxi6 libxtst6 \
    libappindicator3-1 libasound2 \
    # Utilities
    curl ca-certificates xdg-utils fonts-liberation \
    && ln -s /usr/bin/chromium /usr/bin/chromium-browser \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install UV package manager
RUN pip install --no-cache-dir uv

# ========================================
# Dependency installation (heavily cached)
# Split into torch (large/slow) vs rest (fast)
# ========================================
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./

# Step 1: Install CPU-only torch FIRST before anything else.
# These wheels do NOT include libtorch_cuda.so (saves ~3GB vs CUDA wheels).
# Layer is only rebuilt when uv.lock changes.
RUN uv pip install --system --no-cache \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# Step 2: Write a constraints file pinning torch to the CPU versions already installed,
# then install the rest of the project dependencies. This prevents whisperx from
# overriding torch with a CUDA variant.
RUN pip show torch | grep '^Version:' | awk '{print "torch==" $2 "\ntorchvision\ntorchaudio"}' > /tmp/constraints.txt && cat /tmp/constraints.txt
RUN uv pip install --system --no-cache \
    --extra-index-url https://pypi.org/simple \
    --constraint /tmp/constraints.txt \
    -r pyproject.toml

# Aggressively remove nvidia/cuda junk that whisperx might have sneaked in
RUN find /usr/local/lib/python3.12/site-packages -type d -name "nvidia" -exec rm -rf {} + 2>/dev/null || true
RUN find /usr/local/lib/python3.12/site-packages -name "*cuda*" -not -path "*/torch/*" -exec rm -rf {} + 2>/dev/null || true

# ========================================
# Copy application source (invalidates only when code changes)
# ========================================
COPY src/ ./src/
COPY --from=frontend-builder /build/out/ ./h3xassist-web/out/

# Install the project itself (fast - no-deps)
RUN uv pip install --system --no-cache --no-deps .

# Entrypoint
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Volume mount points
VOLUME ["/root/.config/h3xassist", "/root/.local/share/h3xassist"]

EXPOSE 11411

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:11411/health || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["h3xassist", "service", "run"]
