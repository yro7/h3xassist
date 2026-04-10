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
