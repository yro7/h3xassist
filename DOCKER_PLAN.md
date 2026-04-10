# H3xAssist Docker Implementation Plan

## Executive Summary

Complete Docker containerization of H3xAssist with:
- ✅ Pre-authenticated Microsoft Teams bot account (persistent browser profile)
- ✅ Multi-meeting concurrency (2-3 simultaneous meetings default)
- ✅ PipeWire audio routing via host virtual device
- ✅ Production-ready deployment on any Linux machine
- ✅ WAV export option (opt-in)
- ✅ Local filesystem storage
- ✅ CPU-only inference (MVP)

---

## Architecture Decisions

### Audio System
**Decision**: PipeWire with host virtual device routing

**Rationale**:
- Most modern Linux distributions use PipeWire by default (Ubuntu 22.04+, Fedora 34+, Debian 12+)
- Container can access host audio sockets via volume mount
- Virtual device on host provides clean audio capture point
- No code changes required to audio pipeline

**Implementation**:
- Container includes `pipewire-pulse`, `pipewire-bin`, `pulseaudio-utils`
- Host socket mounted at `/run/pulse/native`
- Host creates virtual sink: `pactl load-module module-null-sink sink_name=h3xassist-monitor`
- Browser outputs to `h3xassist-monitor` sink
- Container captures from `h3xassist-monitor.monitor` source
- Fallback to ALSA via `/dev/snd` device mount

### Browser Authentication
**Decision**: Profile-first architecture with separate authentication phase

**Rationale**:
- Separates authentication lifecycle from recording lifecycle
- Respects existing `ExternalBrowserSession` architecture
- Profiles persist in Docker volume across container restarts
- Session validation before recording prevents failures

**Implementation**:
- **New Module**: `BrowserProfileManager` handles authentication flow
- **Modified**: `ExternalBrowserSession` accepts pre-authenticated profile directory
- **Phase 1 (Auth)**: `h3xassist setup browser-auth --profile teams-bot` with X11 forwarding
- **Phase 2 (Recording)**: Container loads profile automatically, runs headless
- **Session Validation**: Check Teams auth token before joining meetings
- Profile stored in persistent volume: `h3xassist-config`

### Concurrency
**Decision**: 2-3 simultaneous meetings default

**Rationale**:
- Each meeting requires ~500MB-1GB RAM (browser + audio + processing)
- Each meeting requires ~0.5-1 CPU core during recording
- Default configuration balances resource usage and utility

**Resource Guidelines**:
| Meetings | RAM | CPU | Shared Memory |
|----------|-----|-----|---------------|
| 2-3 | 4GB | 2 cores | 2GB |
| 5 | 8GB | 4 cores | 4GB |
| 10 | 16GB | 8 cores | 4GB |

### Storage
**Decision**: Local filesystem storage with lazy model loading

**Rationale**:
- Simpler deployment (no cloud credentials needed)
- Faster I/O for processing
- Full control over data
- Easy backup via volume snapshots
- Models downloaded on first use (lazy loading)

**Structure**:
```
/root/.local/share/h3xassist/
├── meetings/          # Recording directories
├── models/            # WhisperX and AI models (downloaded on demand)
└── schedule.json      # Meeting schedule cache
```

### WAV Export
**Decision**: Opt-in (disabled by default)

**Rationale**:
- Opus is more efficient (smaller files, good quality)
- WAV is larger (~10x) but more compatible
- Users can enable when needed for specific workflows

---

## File Structure

```
h3xassist/
├── Dockerfile                      # Multi-stage Docker build
├── docker-compose.yml              # Docker Compose configuration
├── .dockerignore                   # Docker build exclusions
├── scripts/
│   ├── deploy.sh                   # Deployment script
│   ├── manage.sh                   # Management commands
│   ├── teams-auth.sh               # Teams authentication helper
│   ├── docker-audio-check.sh       # Audio diagnostics
│   └── setup-audio.sh              # Host audio virtual device setup
├── DOCKER_PLAN.md                  # This file
├── DOCKER.md                       # User documentation (to create)
└── src/h3xassist/
    ├── browser/
    │   ├── profiles.py             # Existing profile storage
    │   └── auth.py                 # NEW: BrowserProfileManager
    ├── audio/
    │   └── virtual.py              # Virtual device management
    └── cli/
        └── setup.py                # Add browser-auth command
```

---

## Implementation Details

### 1. Dockerfile

```dockerfile
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

# Pre-download AI models removed - models now download on first use (lazy loading)

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
```

---

### 2. docker-compose.yml

```yaml
version: '3.8'

services:
  h3xassist:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: h3xassist-bot
    ports:
      - "11411:11411"
    volumes:
      # Configuration and browser profiles (PERSISTENT - authenticated sessions)
      - h3xassist-config:/root/.config/h3xassist
      # Recordings and models (PERSISTENT - your data)
      - h3xassist-data:/root/.local/share/h3xassist
      # Audio socket from host (CRITICAL for audio capture)
      - /run/pulse/native:/run/pulse/native
      - /run/user/1000/pulse:/run/pulse:ro
      # PipeWire runtime (required for some systems)
      - /run/pipewire:/run/pipewire:ro
      # X11 display for authentication
      - /tmp/.X11-unix:/tmp/.X11-unix:ro
    environment:
      # Audio configuration
      - PULSE_SERVER=unix:/run/pulse/native
      - XDG_RUNTIME_DIR=/run/pulse
      # Display for browser authentication (only needed during auth phase)
      - DISPLAY=${DISPLAY:-:99}
      # Audio virtual device name for capture
      - H3XASSIST__AUDIO__VIRTUAL_DEVICE_NAME=h3xassist-monitor
      # Application settings
      - H3XASSIST_LOG=INFO
      # Optional: Override settings via environment
      # - H3XASSIST__GENERAL__MEETING_DISPLAY_NAME=Teams Bot
      # - H3XASSIST__HTTP__PORT=11411
      # - H3XASSIST__BROWSER__STABILITY_PROFILE=default
    devices:
      # Direct audio device access (fallback if PipeWire fails)
      - /dev/snd:/dev/snd
    security_opt:
      - seccomp:unconfined  # Required for Chromium sandbox
    shm_size: '2gb'  # Shared memory for Chromium
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11411/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

volumes:
  h3xassist-config:
    driver: local
    name: h3xassist-config
  h3xassist-data:
    driver: local
    name: h3xassist-data

networks:
  default:
    name: h3xassist-network
```

---

### 3. .dockerignore

```
.git
.gitignore
*.md
!README.md
!DOCKER.md
!DOCKER_PLAN.md
.h3xassist/
*.log
*.pyc
__pycache__/
.mypy_cache/
.ruff_cache/
.pytest_cache/
.venv/
venv/
h3xassist-web/node_modules/
h3xassist-web/.next/
h3xassist-web/out/
.env
.env.*
!.env.example
tests/
*.tar.gz
backup/
```

---

### 4. scripts/docker-entrypoint.sh

```bash
#!/bin/bash
set -e

echo "🚀 H3xAssist Docker Entrypoint"
echo "==============================="

# Check if this is first run (no settings file)
SETTINGS_FILE="/root/.config/h3xassist/settings.yaml"
if [ ! -f "$SETTINGS_FILE" ]; then
    echo "⚠️  No settings file found at $SETTINGS_FILE"
    echo "   Please configure settings via web interface or mount settings.yaml"
    echo ""
    echo "   Example settings.yaml:"
    echo "   models:"
    echo "     hf_token: 'your_huggingface_token'"
    echo "   summarization:"
    echo "     provider_token: 'your_google_api_key'"
    echo ""
    echo "   Mount with: -v /path/to/settings.yaml:$SETTINGS_FILE"
    echo ""
    echo "⏳ Waiting 10 seconds before continuing..."
    sleep 10
fi

# Check if models directory exists (lazy loading - models download on first use)
MODELS_DIR="/root/.local/share/h3xassist/models"
if [ ! -d "$MODELS_DIR" ]; then
    echo "📦 Models directory will be created on first use"
    echo "   First recording will download AI models (this may take several minutes)"
    mkdir -p "$MODELS_DIR"
fi

# Audio setup check
if [ ! -S /run/pulse/native ]; then
    echo "⚠️  Warning: PulseAudio socket not found"
    echo "   Audio recording may not work"
    echo "   Ensure host has PipeWire/PulseAudio running"
    echo "   Mount with: -v /run/pulse/native:/run/pulse/native"
    echo ""
fi

echo "✅ Starting H3xAssist service..."
echo ""

# Execute the main command
exec "$@"
```

---

### 5. scripts/setup-audio.sh

```bash
#!/bin/bash
# Host script to setup audio virtual device for H3xAssist
# Run this ONCE on the host before starting Docker container

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔊 H3xAssist Audio Setup${NC}"
echo "=========================="
echo ""

# Check for PipeWire/PulseAudio
if ! command -v pactl &> /dev/null; then
    echo -e "${RED}❌ pactl not found${NC}"
    echo "   Install PipeWire/PulseAudio first:"
    echo "   Ubuntu/Debian: sudo apt install pipewire-pulse pulseaudio-utils"
    echo "   Fedora: sudo dnf install pipewire-pulse pulseaudio-utils"
    exit 1
fi

# Check if PipeWire/PulseAudio is running
if ! pactl info &> /dev/null; then
    echo -e "${RED}❌ PipeWire/PulseAudio is not running${NC}"
    echo "   Start the audio service first"
    exit 1
fi

echo -e "${GREEN}✓${NC} PipeWire/PulseAudio detected"

# Check for existing h3xassist virtual device
EXISTING=$(pactl list short sinks | grep -c "h3xassist-monitor" || echo "0")
if [ "$EXISTING" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Virtual device 'h3xassist-monitor' already exists${NC}"
    echo "   Remove it first with:"
    echo "   pactl unload-module module-null-sink"
    echo ""
    read -p "Remove existing device and recreate? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Find and unload the module
        MODULE_ID=$(pactl list short modules | grep "module-null-sink" | grep "h3xassist-monitor" | cut -f1)
        if [ -n "$MODULE_ID" ]; then
            pactl unload-module $MODULE_ID
            echo "Removed existing virtual device"
        fi
    else
        echo "Aborted"
        exit 0
    fi
fi

# Create virtual device
echo "Creating virtual sink 'h3xassist-monitor'..."
if pactl load-module module-null-sink sink_name=h3xassist-monitor sink_properties="device.description='H3xAssist Monitor'" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Virtual device created successfully"
else
    echo -e "${RED}❌ Failed to create virtual device${NC}"
    echo "   Try running with sudo if permission denied"
    exit 1
fi

# Verify device is working
echo ""
echo "Testing audio capture..."
DEFAULT_SINK=$(pactl get-default-sink)
echo "Current default sink: $DEFAULT_SINK"

echo ""
echo -e "${GREEN}✅ Audio setup complete!${NC}"
echo ""
echo "📝 Next steps:"
echo "1. Start Docker container with audio socket mounted:"
echo "   docker-compose up -d"
echo ""
echo "2. In Teams meeting, select audio output: 'H3xAssist Monitor'"
echo "   (or set as default before meeting starts)"
echo ""
echo "3. Container will capture audio from 'h3xassist-monitor.monitor'"
echo ""
echo "⚠️  Note: Virtual device is lost on host reboot"
echo "   Re-run this script after reboot, or add to startup:"
echo "   systemctl --user create h3xassist-audio.service"
echo ""
```

---

### 6. scripts/deploy.sh

```bash
#!/bin/bash
set -e

echo "🚀 H3xAssist Docker Deployment"
echo "=============================="
echo ""

# Configuration
CONTAINER_NAME="h3xassist-bot"
IMAGE_NAME="h3xassist:latest"
CONFIG_VOLUME="h3xassist-config"
DATA_VOLUME="h3xassist-data"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose.${NC}"
    exit 1
fi

# Check for PipeWire/PulseAudio
if [ ! -S /run/pulse/native ] && [ ! -S /run/user/1000/pulse/native ]; then
    echo -e "${YELLOW}⚠️  Warning: PulseAudio socket not found${NC}"
    echo "   Audio recording may not work"
    echo "   Ensure PipeWire/PulseAudio is running on host"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Build image
echo ""
echo "🔨 Building Docker image..."
docker-compose build

# Create volumes if they don't exist
echo ""
echo "💾 Creating volumes..."
docker volume create $CONFIG_VOLUME
docker volume create $DATA_VOLUME

# Start service
echo ""
echo "🎯 Starting H3xAssist service..."
docker-compose up -d

# Wait for service to be healthy
echo ""
echo "⏳ Waiting for service to become healthy..."
for i in {1..30}; do
    if curl -s http://localhost:11411/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Service is healthy!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠️  Service may not be fully ready yet${NC}"
    fi
    sleep 2
done

# Show status
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "🌐 Web interface: http://localhost:11411"
echo ""
echo "📝 Next steps:"
echo "   1. Configure settings in web interface"
echo "   2. Authenticate Teams bot account:"
echo "      ./scripts/teams-auth.sh"
echo "   3. Create your first recording!"
echo ""
```

---

### 7. scripts/manage.sh

```bash
#!/bin/bash

CONTAINER_NAME="h3xassist-bot"
COMMAND="${1:-help}"
shift || true

case $COMMAND in
    start)
        echo "Starting H3xAssist..."
        docker-compose up -d
        ;;
    stop)
        echo "Stopping H3xAssist..."
        docker-compose down
        ;;
    restart)
        echo "Restarting H3xAssist..."
        docker-compose restart
        ;;
    logs)
        docker-compose logs -f
        ;;
    status)
        docker-compose ps
        ;;
    shell)
        docker exec -it $CONTAINER_NAME /bin/bash
        ;;
    auth|teams-auth)
        ./scripts/teams-auth.sh "$@"
        ;;
    backup)
        echo "Backing up configuration and data..."
        BACKUP_DIR="./backup/$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        docker run --rm \
            -v h3xassist-config:/source:ro \
            -v "$BACKUP_DIR":/dest \
            alpine tar czf /dest/config.tar.gz -C /source .
        
        docker run --rm \
            -v h3xassist-data:/source:ro \
            -v "$BACKUP_DIR":/dest \
            alpine tar czf /dest/data.tar.gz -C /source .
        
        echo "Backup complete: $BACKUP_DIR"
        ;;
    restore)
        BACKUP_FILE="$1"
        if [ -z "$BACKUP_FILE" ]; then
            echo "Usage: $0 restore <backup-dir>"
            echo "Example: $0 restore ./backup/20250110-120000"
            exit 1
        fi
        
        echo "Restoring from $BACKUP_FILE..."
        
        if [ -f "$BACKUP_FILE/config.tar.gz" ]; then
            docker run --rm \
                -v h3xassist-config:/dest \
                -v "$BACKUP_FILE":/source:ro \
                alpine tar xzf /source/config.tar.gz -C /dest
            echo "Config restored"
        fi
        
        if [ -f "$BACKUP_FILE/data.tar.gz" ]; then
            docker run --rm \
                -v h3xassist-data:/dest \
                -v "$BACKUP_FILE":/source:ro \
                alpine tar xzf /source/data.tar.gz -C /dest
            echo "Data restored"
        fi
        
        echo "Restore complete"
        ;;
    health)
        curl -s http://localhost:11411/health
        ;;
    audio-check)
        docker exec -it $CONTAINER_NAME /app/scripts/docker-audio-check.sh
        ;;
    validate-profile)
        docker exec -it $CONTAINER_NAME h3xassist validate-profile --online "$@"
        ;;
    clean)
        echo "Cleaning up unused resources..."
        docker-compose down -v
        docker system prune -f
        echo "Cleanup complete"
        ;;
    *)
        echo "H3xAssist Docker Management"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  start       - Start the service"
        echo "  stop        - Stop the service"
        echo "  restart     - Restart the service"
        echo "  logs        - View logs (Ctrl+C to exit)"
        echo "  status      - Show container status"
        echo "  shell       - Open shell in container"
        echo "  auth        - Authenticate Teams bot"
        echo "  backup      - Backup configuration and data"
        echo "  restore     - Restore from backup"
        echo "  health      - Check service health"
        echo "  audio-check - Check audio setup"
        echo "  validate-profile - Validate browser profile session"
        echo "  clean       - Remove container and volumes"
        echo ""
        ;;
esac
```

---

### 8. scripts/teams-auth.sh

```bash
#!/bin/bash
set -e

CONTAINER_NAME="h3xassist-bot"
PROFILE="${1:-teams-bot}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🔐 Teams Bot Authentication${NC}"
echo -e "${CYAN}===========================${NC}"
echo ""

# Check if container is running
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${RED}❌ Container $CONTAINER_NAME is not running${NC}"
    echo "   Start with: docker-compose up -d"
    exit 1
fi

# Check for X11 display
if [ -n "$DISPLAY" ]; then
    echo -e "${GREEN}🖥️  X11 display detected: $DISPLAY${NC}"
    echo ""
    echo -e "${CYAN}Opening browser for authentication...${NC}"
    echo "1. Log into your Teams account"
    echo "2. Wait for Teams interface to load completely"
    echo "3. Close browser when done"
    echo ""
    
    docker exec \
        -e DISPLAY=$DISPLAY \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -it $CONTAINER_NAME \
        h3xassist teams-auth-docker --profile "$PROFILE"
else
    echo -e "${YELLOW}⚠️  No X11 display detected${NC}"
    echo ""
    echo "Options:"
    echo ""
    echo "1. Run with X11 forwarding (recommended):"
    echo "   xhost +local:docker  # Allow Docker X11 access"
    echo "   $0 $PROFILE"
    echo ""
    echo "2. Manual profile mount (headless servers):"
    echo "   docker-compose down"
    echo "   docker run -it --rm \\"
    echo "     -v h3xassist-config:/root/.config/h3xassist \\"
    echo "     -e DISPLAY=\$DISPLAY \\"
    echo "     -v /tmp/.X11-unix:/tmp/.X11-unix \\"
    echo "     h3xassist:latest h3xassist teams-auth"
    echo "   docker-compose up -d"
    echo ""
    read -p "Continue without X11? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Attempting authentication anyway..."
        docker exec -it $CONTAINER_NAME h3xassist teams-auth --profile "$PROFILE"
    else
        echo "Aborted"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✅ Authentication complete!${NC}"
echo "   Profile saved: $PROFILE"
echo ""
echo "Next steps:"
echo "1. In web interface, select profile '$PROFILE' when creating recordings"
echo "2. Bot will use authenticated session to join meetings"
echo ""
```

---

### 9. scripts/docker-audio-check.sh

```bash
#!/bin/bash
# Check audio setup in Docker container

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== H3xAssist Docker Audio Check ==="
echo ""

# Check PulseAudio socket
if [ -S /run/pulse/native ]; then
    echo -e "${GREEN}✓${NC} PulseAudio socket found: /run/pulse/native"
else
    echo -e "${RED}✗${NC} PulseAudio socket NOT found"
    echo "  Mount with: -v /run/pulse/native:/run/pulse/native"
fi

# Check pactl
if command -v pactl &> /dev/null; then
    echo -e "${GREEN}✓${NC} pactl available"
    default_sink=$(pactl get-default-sink 2>/dev/null || echo "unknown")
    echo "  Default sink: $default_sink"
else
    echo -e "${RED}✗${NC} pactl NOT found"
fi

# Check pw-dump
if command -v pw-dump &> /dev/null; then
    echo -e "${GREEN}✓${NC} pw-dump available"
    sinks=$(pw-dump 2>/dev/null | grep -c '"media.class": "Audio/Sink"' || echo "0")
    echo "  Available sinks: $sinks"
else
    echo -e "${YELLOW}⚠${NC} pw-dump NOT found"
fi

# Check ffmpeg
if command -v ffmpeg &> /dev/null; then
    echo -e "${GREEN}✓${NC} ffmpeg available"
    ffmpeg_version=$(ffmpeg -version | head -1)
    echo "  Version: $ffmpeg_version"
else
    echo -e "${RED}✗${NC} ffmpeg NOT found"
fi

# Check Chromium
if command -v chromium-browser &> /dev/null; then
    echo -e "${GREEN}✓${NC} chromium-browser available"
elif command -v chromium &> /dev/null; then
    echo -e "${GREEN}✓${NC} chromium available"
else
    echo -e "${RED}✗${NC} Chromium NOT found"
fi

# Test sink creation
echo ""
echo "Testing null sink creation..."
if pactl load-module module-null-sink sink_name=test_sink 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Null sink creation successful"
    pactl unload-module module-null-sink 2>/dev/null
    echo "  (test sink cleaned up)"
else
    echo -e "${RED}✗${NC} Null sink creation FAILED"
    echo "  Check PipeWire is running on host"
fi

echo ""
echo "=== Check Complete ==="
```

---

### 10. Browser Profile Manager (src/h3xassist/browser/auth.py)

**NEW MODULE** - Handles browser authentication lifecycle separately from recording.

```python
"""Browser profile authentication management.

This module provides authentication lifecycle management for browser profiles,
separate from the recording lifecycle handled by ExternalBrowserSession.

Usage:
    # Authenticate a new profile (interactive)
    manager = BrowserProfileManager()
    await manager.authenticate("teams-bot")
    
    # Load and validate existing profile
    profile = manager.load_profile("teams-bot")
    if not manager.validate_session("teams-bot"):
        await manager.reauthenticate("teams-bot")
"""

import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import json
import logging

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeout

from h3xassist.browser.session import ExternalBrowserSession
from h3xassist.browser.profiles import ProfileManager
from h3xassist.settings import settings

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when browser authentication fails."""


class SessionExpiredError(Exception):
    """Raised when saved session has expired."""


class BrowserProfileManager:
    """Manages browser profile authentication lifecycle.
    
    Responsibilities:
    - Interactive authentication flows (MFA/2FA support)
    - Session validation before recording
    - Session expiration detection
    - Profile re-authentication
    
    Architecture:
    - Works with existing ExternalBrowserSession
    - Profiles stored in standard profile directory
    - Session metadata cached in profile directory
    """
    
    def __init__(self, profiles_dir: Optional[str] = None):
        self.profiles_dir = Path(profiles_dir) if profiles_dir else Path(settings.browser.profiles_base_dir).expanduser()
        self.profile_manager = ProfileManager()
    
    async def authenticate(
        self,
        profile_name: str,
        target_url: str = "https://teams.microsoft.com",
        timeout: float = 300.0,
    ) -> None:
        """Authenticate browser profile interactively.
        
        Opens browser window for user to complete login flow including MFA/2FA.
        Session is saved to profile directory for reuse.
        
        Args:
            profile_name: Name for the authenticated profile
            target_url: URL to navigate to for authentication
            timeout: Maximum time to wait for authentication (seconds)
        """
        profile_path = self.profiles_dir / profile_name
        
        logger.info(f"Starting authentication for profile: {profile_name}")
        logger.info(f"Profile location: {profile_path}")
        
        session = ExternalBrowserSession(
            browser_bin="chromium-browser",
            env=dict(asyncio.get_event_loop().env),
            profile_dir=str(profile_path),
            automation_mode=False,  # Allow user interaction
            headless=False,  # Must be visible for login
            stability_profile="default",  # No automation flags
        )
        
        async with session:
            page = await session.wait_page(5.0)
            
            logger.info(f"Navigating to {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            
            logger.info("Waiting for user to complete authentication...")
            logger.info("Close the browser window when finished.")
            
            # Wait for user to complete login and close browser
            try:
                await asyncio.wait_for(
                    session.wait_closed(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Authentication timeout after {timeout}s")
                raise AuthenticationError(f"Authentication timed out after {timeout} seconds")
        
        # Save authentication metadata
        self._save_auth_metadata(profile_name, target_url)
        
        logger.info(f"Authentication complete for profile: {profile_name}")
    
    def _save_auth_metadata(self, profile_name: str, target_url: str) -> None:
        """Save authentication metadata for session validation."""
        metadata_file = self.profiles_dir / profile_name / "auth_metadata.json"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        
        metadata = {
            "profile_name": profile_name,
            "target_url": target_url,
            "authenticated_at": datetime.now().isoformat(),
            "last_validated": None,
        }
        
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
    
    def load_profile(self, profile_name: str) -> Optional[dict]:
        """Load profile authentication metadata.
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            Profile metadata dict or None if not found
        """
        metadata_file = self.profiles_dir / profile_name / "auth_metadata.json"
        
        if not metadata_file.exists():
            return None
        
        with open(metadata_file, "r") as f:
            return json.load(f)
    
    def validate_session(self, profile_name: str) -> bool:
        """Validate if saved session is still active.
        
        Performs lightweight validation:
        - Check profile directory exists
        - Check authentication metadata exists
        - Check session age (warn if > 30 days)
        
        For full validation, use validate_session_online()
        
        Args:
            profile_name: Name of the profile to validate
            
        Returns:
            True if session appears valid, False if re-authentication needed
        """
        profile_path = self.profiles_dir / profile_name
        
        # Check profile directory exists
        if not profile_path.exists():
            logger.warning(f"Profile directory not found: {profile_path}")
            return False
        
        # Check metadata exists
        metadata = self.load_profile(profile_name)
        if not metadata:
            logger.warning(f"Profile metadata not found: {profile_name}")
            return False
        
        # Check session age
        authenticated_at = datetime.fromisoformat(metadata["authenticated_at"])
        age = datetime.now() - authenticated_at
        
        if age > timedelta(days=90):
            logger.warning(f"Profile {profile_name} is {age.days} days old, may need re-authentication")
            # Still return True, but log warning
        
        logger.info(f"Profile {profile_name} validation passed (age: {age.days} days)")
        return True
    
    async def validate_session_online(
        self,
        profile_name: str,
        target_url: str = "https://teams.microsoft.com",
    ) -> bool:
        """Validate session by checking authenticated state in browser.
        
        Opens browser with saved profile and checks if still logged in.
        More accurate than validate_session() but slower.
        
        Args:
            profile_name: Name of the profile to validate
            target_url: URL to check authentication against
            
        Returns:
            True if session is valid, False if re-authentication needed
        """
        profile_path = self.profiles_dir / profile_name
        
        if not profile_path.exists():
            return False
        
        session = ExternalBrowserSession(
            browser_bin="chromium-browser",
            env=dict(asyncio.get_event_loop().env),
            profile_dir=str(profile_path),
            automation_mode=True,
            headless=True,
            stability_profile="default",
        )
        
        try:
            async with session:
                page = await session.wait_page(5.0)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                
                # Check for Teams authenticated state
                # Teams sets _ts_ddd_correlation_id when authenticated
                is_authenticated = await page.evaluate("() => !!window._ts_ddd_correlation_id")
                
                if is_authenticated:
                    logger.info(f"Profile {profile_name} session validated online")
                    self._update_validation_timestamp(profile_name)
                    return True
                else:
                    logger.warning(f"Profile {profile_name} session expired (not authenticated)")
                    return False
                    
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return False
        finally:
            await session.close()
    
    def _update_validation_timestamp(self, profile_name: str) -> None:
        """Update last validated timestamp in metadata."""
        metadata = self.load_profile(profile_name)
        if metadata:
            metadata["last_validated"] = datetime.now().isoformat()
            metadata_file = self.profiles_dir / profile_name / "auth_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
    
    async def reauthenticate(
        self,
        profile_name: str,
        target_url: str = "https://teams.microsoft.com",
    ) -> None:
        """Re-authenticate an existing profile.
        
        Convenience method that combines authentication with metadata update.
        
        Args:
            profile_name: Name of the profile to re-authenticate
            target_url: URL for authentication
        """
        logger.info(f"Re-authenticating profile: {profile_name}")
        await self.authenticate(profile_name, target_url)
        logger.info(f"Profile {profile_name} re-authenticated successfully")
```

---

### 11. CLI Commands (src/h3xassist/cli/setup.py additions)

Add the following commands to `src/h3xassist/cli/setup.py`:

```python
@app.command("browser-auth")
def browser_authentication(
    profile: str = typer.Option(
        default="teams-bot",
        help="Profile name for authenticated browser session"
    ),
    target_url: str = typer.Option(
        default="https://teams.microsoft.com",
        help="URL to authenticate against"
    ),
    profiles_dir: str = typer.Option(
        default=settings.browser.profiles_base_dir,
        help="Profiles base directory"
    ),
) -> None:
    """Authenticate browser profile for automated meetings.
    
    This opens a browser window where you can log into your account
    and complete any MFA/2FA flows. The authenticated session is saved
    to the specified profile for reuse in automated recordings.
    """
    from h3xassist.browser.auth import BrowserProfileManager
    
    console.print(Panel(
        "[cyan]Browser Profile Authentication[/cyan]\n\n"
        "This will open a browser window.\n"
        "1. Log into your account\n"
        f"2. Navigate to {target_url}\n"
        "3. Complete any MFA/2FA challenges\n"
        "4. Close the browser when done\n\n"
        "The authenticated session will be saved for automated meetings.",
        style="cyan",
        expand=False
    ))
    
    manager = BrowserProfileManager(profiles_dir=profiles_dir)
    
    async def auth_flow():
        await manager.authenticate(profile, target_url)
    
    try:
        asyncio.run(auth_flow())
        
        console.print(Panel(
            "[ok]Authentication complete![/ok]\n\n"
            f"Profile saved to: {Path(profiles_dir).expanduser() / profile}\n\n"
            "Next steps:\n"
            "1. In web interface, select this profile when creating recordings\n"
            "2. Bot will use authenticated session to join meetings\n"
            "3. Session persists across container restarts",
            style="green",
            expand=False
        ))
    except AuthenticationError as e:
        console.print(Panel(
            f"[error]Authentication failed: {e}[/error]\n\n"
            "Please try again. Ensure you have a stable internet connection.",
            style="red",
            expand=False
        ))
        raise typer.Exit(1)


@app.command("browser-auth-docker")
def browser_authentication_docker(
    profile: str = typer.Option(
        default="teams-bot",
        help="Profile name for authenticated browser session"
    ),
    target_url: str = typer.Option(
        default="https://teams.microsoft.com",
        help="URL to authenticate against"
    ),
) -> None:
    """Authenticate browser profile inside Docker container with X11 forwarding.
    
    Requires Docker container to have X11 forwarding enabled.
    Run with: docker exec -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ...
    """
    import shutil
    
    # Check for X11 display
    display = os.environ.get("DISPLAY")
    if not display:
        console.print(Panel(
            "[error]DISPLAY environment variable not set[/error]\n\n"
            "Run this command with X11 forwarding:\n"
            "docker exec -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix <container> h3xassist browser-auth-docker",
            style="red",
            expand=False
        ))
        raise typer.Exit(1)
    
    # Check for X11 socket
    if not os.path.exists("/tmp/.X11-unix"):
        console.print("[warning]X11 socket not found, but continuing...[/warning]")
    
    # Use chromium-browser if available
    browser = "chromium-browser" if shutil.which("chromium-browser") else "chromium"
    
    # Reuse the main auth function
    browser_authentication(
        profile=profile,
        target_url=target_url,
        profiles_dir=settings.browser.profiles_base_dir
    )


@app.command("validate-profile")
def validate_profile(
    profile: str = typer.Option(
        default="teams-bot",
        help="Profile name to validate"
    ),
    online: bool = typer.Option(
        default=False,
        help="Perform online validation (opens browser)"
    ),
    profiles_dir: str = typer.Option(
        default=settings.browser.profiles_base_dir,
        help="Profiles base directory"
    ),
) -> None:
    """Validate browser profile session.
    
    Checks if saved authentication session is still valid.
    Use --online flag for accurate validation (opens browser).
    """
    from h3xassist.browser.auth import BrowserProfileManager
    
    manager = BrowserProfileManager(profiles_dir=profiles_dir)
    
    if online:
        console.print(f"[info]Validating profile '{profile}' online...[/info]")
        
        async def validate():
            is_valid = await manager.validate_session_online(profile)
            return is_valid
        
        is_valid = asyncio.run(validate())
        
        if is_valid:
            console.print(Panel(
                f"[ok]Profile '{profile}' is valid and authenticated[/ok]",
                style="green",
                expand=False
            ))
        else:
            console.print(Panel(
                f"[warning]Profile '{profile}' session expired[/warning]\n\n"
                "Re-authenticate with: h3xassist browser-auth --profile {profile}",
                style="yellow",
                expand=False
            ))
    else:
        is_valid = manager.validate_profile(profile)
        
        if is_valid:
            metadata = manager.load_profile(profile)
            if metadata:
                auth_date = datetime.fromisoformat(metadata["authenticated_at"])
                age = (datetime.now() - auth_date).days
                console.print(Panel(
                    f"[ok]Profile '{profile}' appears valid[/ok]\n\n"
                    f"Authenticated: {age} days ago\n"
                    f"Location: {Path(profiles_dir).expanduser() / profile}",
                    style="green",
                    expand=False
                ))
            else:
                console.print(f"[info]Profile '{profile}' directory exists[/info]")
        else:
            console.print(Panel(
                f"[error]Profile '{profile}' not found or invalid[/error]",
                style="red",
                expand=False
            ))
```

---

### 12. WAV Export Configuration (src/h3xassist/settings.py additions)

Add to `AudioSettings` class in `src/h3xassist/settings.py`:

```python
class AudioSettings(BaseModel):
    # ... existing fields ...
    
    # WAV export settings (opt-in)
    export_wav: bool = Field(
        default=False,
        title="Export WAV",
        description="Whether to export recordings as WAV in addition to Opus",
    )
    wav_sample_rate: int = Field(
        default=16000,
        title="WAV sample rate",
        description="Sample rate for WAV export (Hz)",
    )
    wav_bit_depth: int = Field(
        default=16,
        title="WAV bit depth",
        description="Bit depth for WAV export (16 or 24)",
    )
```

---

### 13. WAV Export Implementation (src/h3xassist/meeting_recorder.py additions)

Add to `MeetingRecorder` class in `src/h3xassist/meeting_recorder.py`:

```python
async def _export_wav(self, ogg_path: Path, wav_path: Path) -> None:
    """Convert Opus OGG to WAV format."""
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", str(ogg_path),
        "-ar", str(settings.audio.wav_sample_rate),
        "-sample_fmt", f"s{settings.audio.wav_bit_depth}",
        "-y", str(wav_path),
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        logger.error("WAV export failed: %s", stderr.decode())
        raise RuntimeError(f"WAV conversion failed: {stderr.decode()}")
    
    logger.info("WAV export complete: %s", wav_path)

# In record() method, after recording completes (before return):
if settings.audio.export_wav:
    wav_path = handle.directory / "audio.wav"
    try:
        await self._export_wav(handle.audio, wav_path)
    except Exception as e:
        logger.warning("WAV export failed: %s", e)
```

---

## Deployment Guide

### Quick Start

```bash
# 1. Clone repository
git clone <repository-url>
cd h3xassist

# 2. Make scripts executable
chmod +x scripts/*.sh

# 3. Deploy
./scripts/deploy.sh

# 4. Setup audio virtual device (run ONCE on host)
./scripts/setup-audio.sh

# 5. Deploy
./scripts/deploy.sh

# 6. Authenticate browser profile
./scripts/teams-auth.sh

# 7. Open web interface
open http://localhost:11411
```

### Prerequisites

- **OS**: Linux with PipeWire or PulseAudio (Ubuntu 22.04+, Fedora 34+, Debian 12+)
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **RAM**: 4GB minimum, 8GB recommended (CPU-only inference)
- **Storage**: 10GB for application + models, additional for recordings
- **X11**: For browser authentication (can use SSH X11 forwarding)

### Audio Setup Verification

Before deploying, verify audio system:

```bash
# Check PipeWire/PulseAudio
pactl info

# Check default sink
pactl get-default-sink

# Test audio capture
parec --test | aplay
```

### Audio Virtual Device Setup

Run once on host to create virtual audio device:

```bash
# Create virtual sink for H3xAssist
./scripts/setup-audio.sh

# Verify device created
pactl list short sinks | grep h3xassist

# To remove (cleanup):
pactl unload-module module-null-sink
```

**How it works**:
1. Host creates virtual sink: `h3xassist-monitor`
2. Browser in container outputs audio to `h3xassist-monitor`
3. Container captures from `h3xassist-monitor.monitor` (monitor source)
4. Audio flows: Browser → Host Virtual Sink → Host Virtual Source → Container AudioRecorder

### Post-Deployment

1. **Configure Settings**: Navigate to `http://localhost:11411/settings`

2. **Authenticate Browser Profile**:
   ```bash
   ./scripts/teams-auth.sh
   ```
   This opens browser for interactive login with MFA/2FA support.

3. **Validate Profile** (optional):
   ```bash
   ./scripts/manage.sh validate-profile
   ```

4. **Create First Recording**:
   - Go to web interface
   - Click "New Recording"
   - Select profile: `teams-bot`
   - Enter meeting URL
   - Click "Start Recording"

### Backup Strategy

```bash
# Backup
./scripts/manage.sh backup

# Restore
./scripts/manage.sh restore ./backup/20250110-120000
```

### Troubleshooting

#### No Audio
```bash
# Check audio socket
docker exec h3xassist-bot ls -la /run/pulse/native

# Check PipeWire
docker exec h3xassist-bot pw-dump | head -20

# Run audio check
./scripts/manage.sh audio-check
```

#### Browser Crashes
```bash
# Check logs
docker-compose logs h3xassist | grep -i "browser\|crash"

# Try software rendering
# Edit docker-compose.yml, add:
# environment:
#   - H3XASSIST__BROWSER__STABILITY_PROFILE=software_safe
docker-compose restart
```

#### Authentication Session Expired
```bash
# Validate profile
./scripts/manage.sh validate-profile

# Re-authenticate if needed
./scripts/teams-auth.sh
```

#### First Recording Very Slow
```bash
# This is normal - models are downloading on first use
# Check download progress in logs:
docker-compose logs -f | grep -i "download\|model"

# Models persist in h3xassist-data volume
# Subsequent recordings will be fast
```

#### Container Won't Start
```bash
# Check logs
docker-compose logs

# Check port conflict
sudo lsof -i :11411

# Clean restart
./scripts/manage.sh clean
./scripts/deploy.sh
```

---

## Resource Allocation

### Default Configuration (2-3 meetings)

```yaml
# docker-compose.yml
services:
  h3xassist:
    shm_size: '2gb'
    # No explicit CPU/memory limits
```

### High Concurrency (5+ meetings)

```yaml
# docker-compose.override.yml
services:
  h3xassist:
    shm_size: '4gb'
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
```

---

## Security Considerations

### Container Isolation

**WARNING**: `security_opt: seccomp:unconfined` is required for Chromium but disables syscall filtering.

- This is a security trade-off for browser automation
- Consider using `--cap-add` for finer-grained control instead
- Future enhancement: run as non-root user
- For production: evaluate AppArmor profiles

### Network Security

- Default: localhost only (127.0.0.1:11411)
- For remote access: use reverse proxy with TLS (nginx, traefik)
- Consider firewall rules for port 11411
- WebSocket connections require upgrade headers in proxy

### Data Protection

- Browser profiles stored in Docker volume (encrypted at host level recommended)
- Recordings stored in Docker volume
- Backup regularly with encryption
- Consider encryption for sensitive recordings
- HuggingFace token stored in settings.yaml (mount as secret)

### Secrets Management

**Recommended**: Mount settings file with sensitive data:
```bash
# Create settings with credentials
cat > ~/.config/h3xassist/settings.yaml << EOF
models:
  hf_token: 'your_huggingface_token_here'
summarization:
  provider_token: 'your_google_api_key_here'
integrations:
  outlook:
    client_id: 'your_client_id'
    client_secret: 'your_client_secret'
EOF

# Mount as read-only
docker run -v ~/.config/h3xassist/settings.yaml:/root/.config/h3xassist/settings.yaml:ro ...
```

**Alternative**: Use Docker secrets (Swarm mode) or environment variables.

---

## Future Enhancements

### Phase 2 (Post-MVP)
- [ ] Multi-bot support (multiple Teams accounts)
- [ ] Cloud storage integration (S3, GCS)
- [ ] Prometheus metrics export
- [ ] Grafana dashboard
- [ ] Automated session refresh

### Phase 3 (Advanced)
- [ ] Kubernetes deployment
- [ ] Load balancing across containers
- [ ] Redis session storage
- [ ] Horizontal scaling
- [ ] WebSocket clustering

---

## Testing Checklist

### Pre-Deployment
- [ ] Docker installed and running
- [ ] Docker Compose installed
- [ ] PipeWire/PulseAudio running on host
- [ ] X11 forwarding available (for auth)
- [ ] Sufficient disk space (10GB+)
- [ ] Sufficient RAM (4GB+)
- [ ] Audio virtual device setup: `./scripts/setup-audio.sh`

### Post-Deployment
- [ ] Service healthy: `curl http://localhost:11411/health`
- [ ] Web interface accessible
- [ ] Audio check passes: `./scripts/manage.sh audio-check`
- [ ] Virtual device visible in container: `pactl list short sinks`
- [ ] Browser authentication works: `./scripts/teams-auth.sh`
- [ ] Profile validation works: `./scripts/manage.sh validate-profile`
- [ ] Can create recording
- [ ] Can stop recording (graceful)
- [ ] Can cancel recording (immediate)
- [ ] Post-processing completes (first run downloads models)
- [ ] Summary generated
- [ ] Models cached for subsequent recordings

### Stress Testing
- [ ] 2 concurrent meetings
- [ ] 3 concurrent meetings
- [ ] Long meeting (2+ hours)
- [ ] Container restart preserves sessions
- [ ] Backup/restore works

---

## Success Criteria

### MVP Complete When:
1. ✅ Docker container builds successfully
2. ✅ Service starts and health check passes
3. ✅ Audio virtual device created on host
4. ✅ Audio recording works in container (captures from virtual device)
5. ✅ Browser authentication flow works (browser-auth command)
6. ✅ Browser profile persists across restarts
7. ✅ Profile validation works (online and offline)
8. ✅ Can record single meeting
9. ✅ Can record 2-3 concurrent meetings
10. ✅ Post-processing completes (lazy model loading on first use)
11. ✅ Web interface fully functional
12. ✅ Backup/restore works

### Production Ready When:
1. ✅ All MVP criteria met
2. ✅ Documentation complete (DOCKER.md)
3. ✅ Automated deployment script works
4. ✅ Audio setup script tested on multiple distributions
5. ✅ Backup strategy tested
6. ✅ Resource limits defined
7. ✅ Security review completed (seccomp, secrets management)

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)

**1.1 Dockerfile and Build System**
- [ ] Create multi-stage Dockerfile
- [ ] Configure system dependencies (PipeWire, Chromium, FFmpeg)
- [ ] Add entrypoint script for first-run setup
- [ ] Test build process

**1.2 Audio System**
- [ ] Create `scripts/setup-audio.sh` for host virtual device
- [ ] Test audio routing: Browser → Host Virtual Sink → Container
- [ ] Add `docker-audio-check.sh` diagnostics
- [ ] Verify audio capture in container

**1.3 Docker Compose Configuration**
- [ ] Define volume mounts (config, data, audio socket)
- [ ] Configure environment variables
- [ ] Set up health checks
- [ ] Test container startup

### Phase 2: Browser Authentication (Week 2-3)

**2.1 BrowserProfileManager Module**
- [ ] Create `src/h3xassist/browser/auth.py`
- [ ] Implement `authenticate()` method
- [ ] Implement `validate_session()` methods (offline and online)
- [ ] Add session metadata storage

**2.2 CLI Commands**
- [ ] Add `h3xassist browser-auth` command
- [ ] Add `h3xassist browser-auth-docker` command
- [ ] Add `h3xassist validate-profile` command
- [ ] Test authentication flow with X11 forwarding

**2.3 Profile Persistence**
- [ ] Test profile save/load across container restarts
- [ ] Implement session expiration detection
- [ ] Add re-authentication workflow

### Phase 3: Integration and Testing (Week 3-4)

**3.1 End-to-End Recording**
- [ ] Test single meeting recording
- [ ] Verify audio capture and encoding
- [ ] Test post-processing with lazy model loading
- [ ] Verify summary generation

**3.2 Concurrency**
- [ ] Test 2 concurrent meetings
- [ ] Test 3 concurrent meetings
- [ ] Monitor resource usage (RAM, CPU)
- [ ] Optimize shared memory settings

**3.3 Management Scripts**
- [ ] Complete `deploy.sh` with audio setup
- [ ] Enhance `manage.sh` with profile validation
- [ ] Update `teams-auth.sh` to use BrowserProfileManager
- [ ] Test backup/restore workflow

### Phase 4: Documentation and Polish (Week 4-5)

**4.1 User Documentation**
- [ ] Create `DOCKER.md` with setup guide
- [ ] Document audio troubleshooting
- [ ] Add FAQ section
- [ ] Create quick start examples

**4.2 Security Review**
- [ ] Evaluate seccomp alternatives
- [ ] Document secrets management options
- [ ] Test encrypted volume storage
- [ ] Review network security (firewall, TLS)

**4.3 Production Readiness**
- [ ] Test on multiple Linux distributions
- [ ] Verify PipeWire compatibility (Ubuntu, Fedora, Debian)
- [ ] Stress test with long meetings (2+ hours)
- [ ] Document resource requirements

---

## Key Technical Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Audio System | Host virtual device + monitor capture | Works with existing code, no rework needed |
| Browser Auth | Profile-first with separate module | Respects architecture, clean separation |
| Model Loading | Lazy (on first use) | Simpler Dockerfile, models persist in volume |
| GPU Acceleration | CPU-only for MVP | Simpler deployment, CUDA adds complexity |
| Security | seccomp:unconfined (trade-off) | Required for Chromium, documented risk |
| Storage | Local filesystem via volumes | Simple, fast, easy backup |

---

## Contact & Support

- Documentation: `DOCKER.md` (to create)
- Logs: `docker-compose logs -f`
- Health: `curl http://localhost:11411/health`
- Management: `./scripts/manage.sh`
- Audio Setup: `./scripts/setup-audio.sh`
- Profile Auth: `./scripts/teams-auth.sh`

---

*Last updated: 2025-01-10*
*Version: 2.0.0 (Docker-native with audio routing and profile auth)*
