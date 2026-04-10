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
