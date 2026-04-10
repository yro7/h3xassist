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
