#!/bin/bash
# Host script to setup audio virtual device for H3xAssist
# Run this ONCE on the host before starting Docker container

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔊 H3xAssist Audio Setup${NC}"
echo "=========================="
echo ""

# Get user info
CURRENT_USER=$(whoami)
USER_ID=$(id -u)

# Check for PipeWire/PulseAudio and install if missing
if ! command -v pactl &> /dev/null; then
    echo -e "${YELLOW}⚠️  PipeWire/PulseAudio not found, installing...${NC}"
    echo ""
    
    # Detect package manager
    if command -v apt &> /dev/null; then
        echo "Installing with apt..."
        sudo apt update
        sudo apt install -y pipewire pipewire-pulse wireplumber pulseaudio-utils
    elif command -v dnf &> /dev/null; then
        echo "Installing with dnf..."
        sudo dnf install -y pipewire pipewire-pulse wireplumber pulseaudio-utils
    elif command -v pacman &> /dev/null; then
        echo "Installing with pacman..."
        sudo pacman -S --noconfirm pipewire pipewire-pulse wireplumber pulseaudio
    else
        echo -e "${RED}❌ Unsupported package manager${NC}"
        echo "   Please install PipeWire/PulseAudio manually"
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} Installation complete"
    echo ""
fi

# Setup XDG_RUNTIME_DIR if not set
if [ -z "$XDG_RUNTIME_DIR" ]; then
    export XDG_RUNTIME_DIR=/run/user/$USER_ID
    echo -e "${CYAN}ℹ️  Setting XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR${NC}"
fi

# Create runtime directory if it doesn't exist
if [ ! -d "$XDG_RUNTIME_DIR" ]; then
    echo "Creating runtime directory: $XDG_RUNTIME_DIR"
    sudo mkdir -p $XDG_RUNTIME_DIR
    sudo chown $CURRENT_USER:$CURRENT_USER $XDG_RUNTIME_DIR
    chmod 700 $XDG_RUNTIME_DIR
    echo -e "${GREEN}✓${NC} Runtime directory created"
fi

# Check if PipeWire/PulseAudio is running
echo "Checking PipeWire/PulseAudio status..."
if ! pactl info &> /dev/null; then
    echo -e "${YELLOW}⚠️  PipeWire/PulseAudio is not running${NC}"
    echo "   Attempting to start services..."
    echo ""
    
    # Kill any existing instances
    pkill pipewire 2>/dev/null || true
    pkill wireplumber 2>/dev/null || true
    
    sleep 1
    
    # Try systemd first
    if command -v systemctl &> /dev/null && systemctl --user status &> /dev/null; then
        echo "Starting with systemd --user..."
        systemctl --user start pipewire pipewire-pulse wireplumber || true
        sleep 2
        
        if pactl info &> /dev/null; then
            echo -e "${GREEN}✓${NC} Services started via systemd"
        fi
    fi
    
    # Fallback to manual start
    if ! pactl info &> /dev/null; then
        echo "Starting services manually..."
        pipewire &
        pipewire-pulse &
        wireplumber &
        sleep 3
        
        if pactl info &> /dev/null; then
            echo -e "${GREEN}✓${NC} Services started manually"
        else
            echo -e "${RED}❌ Failed to start PipeWire/PulseAudio${NC}"
            echo "   Try logging out and back in, or rebooting"
            exit 1
        fi
    fi
else
    echo -e "${GREEN}✓${NC} PipeWire/PulseAudio is running"
fi

echo -e "${GREEN}✓${NC} PipeWire/PulseAudio detected"

# Check for existing h3xassist virtual device
EXISTING=$(pactl list short sinks | grep -c "h3xassist-monitor" 2>/dev/null || echo "0")
EXISTING=$(echo "$EXISTING" | tr -d '[:space:]')
if [ "$EXISTING" -gt 0 ] 2>/dev/null; then
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
