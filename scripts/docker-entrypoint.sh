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
rm -f /run/user/0/pulse/native
if [ ! -S /run/pulse/native ] && [ ! -S /run/user/0/pulse/native ]; then
    echo "⚠️  No host PulseAudio socket found. Starting local PipeWire daemon inside container for headless operation..."
    # Start pipewire daemon in background to handle audio routing internally
    mkdir -p /run/user/0
    export XDG_RUNTIME_DIR=/run/user/0
    pipewire &
    sleep 1
    pipewire-pulse &
    sleep 2
    
    # Set the new PULSE_SERVER to point to the local instance's default path if needed
    export PULSE_SERVER=unix:/run/user/0/pulse/native
    
    # Create the virtual sink required by the application
    pactl load-module module-null-sink sink_name=h3xassist-monitor sink_properties=device.description="H3XAssist_Virtual_Monitor" || true
fi

echo "✅ Starting H3xAssist service..."
echo ""

# Execute the main command
exec "$@"
