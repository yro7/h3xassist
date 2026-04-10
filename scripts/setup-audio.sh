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
