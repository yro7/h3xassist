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

if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose.${NC}"
    exit 1
fi

# Note: PipeWire audio setup is now handled automatically inside the container.
# External audio routing from host is optional and depends on your environment.
if [ ! -S /run/pulse/native ] && [ ! -S /run/user/1000/pulse/native ]; then
    echo -e "${YELLOW}ℹ️  Host audio socket not detected. The bot will use its internal audio pipeline.${NC}"
fi

# Build image with BuildKit for better performance
echo ""
echo "🔨 Building Docker image..."
DOCKER_BUILDKIT=1 docker compose build

# Start service
echo ""
echo "🎯 Starting H3xAssist service..."
docker compose up -d

# Initialize required state
echo ""
echo "⚙️  Initializing application state..."
# Wait for container to be ready
for i in {1..10}; do
    if docker compose ps h3xassist | grep -q "Up"; then
        # Create default browser profile directory if it doesn't exist
        docker compose exec h3xassist mkdir -p /root/.config/h3xassist/browser-profiles/default
        echo "✅ State initialized"
        break
    fi
    echo "   Waiting for container to stabilize... ($i/10)"
    sleep 2
done

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
docker compose ps

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
