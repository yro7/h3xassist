# ========================================
# Stage 1: Build Frontend
# ========================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY h3xassist-web/package.json h3xassist-web/pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source
COPY h3xassist-web/ ./

# Build frontend
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

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Audio processing
    ffmpeg=7:* \
    pulseaudio-utils=16.1+dfsg~* \
    libpipewire-0.3-0t64=1.0.4* \
    pipewire-bin=1.0.4* \
    pipewire-pulse=1.0.4* \
    # Chromium browser and dependencies
    chromium=149:* \
    chromium-common=149:* \
    chromium-driver=149:* \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    libpango-1.0-0 \
    libcairo2 \
    # Utilities
    curl \
    ca-certificates \
    xdg-utils \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    # Audio capture utilities
    pavucontrol \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install UV package manager
RUN pip install --no-cache-dir uv

# Create application directory
WORKDIR /app

# Copy Python project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Copy built frontend from stage 1
COPY --from=frontend-builder /build/out/ ./h3xassist-web/out/

# Install Python dependencies
RUN uv pip install --system --no-cache .

# Install Playwright browsers (optional, we use system chromium)
# RUN playwright install chromium

# Copy entrypoint script for first-run setup
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Pre-download AI models removed - models download on first use (lazy loading)

# Create volume mount points
VOLUME [ \
    "/root/.config/h3xassist", \
    "/root/.local/share/h3xassist", \
    "/run/pulse/native", \
    "/run/user/0/pulse", \
    "/tmp/.X11-unix" \
]

# Expose API port
EXPOSE 11411

# Health check (wait for longer during first-run model download)
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:11411/health || exit 1

# Entrypoint handles first-run setup
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["h3xassist", "service", "run"]
