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
