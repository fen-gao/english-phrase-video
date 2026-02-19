#!/bin/bash
# ============================================================
# setup.sh - Run this ONCE to set up everything on Manjaro
# ============================================================
set -e

echo "============================================"
echo "  Setting up English Phrases Video Generator"
echo "  for Manjaro Linux"
echo "============================================"
echo ""

# 1. Install system packages
echo "📦 Installing system packages..."
sudo pacman -S --needed --noconfirm python python-pip ffmpeg imagemagick ttf-liberation

# 2. Create project folder
echo ""
echo "📁 Creating project folder..."
mkdir -p ~/english-phrases-video
cd ~/english-phrases-video

# 3. Create Python virtual environment
echo ""
echo "🐍 Creating Python virtual environment..."
python -m venv venv
source venv/bin/activate

# 4. Install Python packages
echo ""
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install edge-tts pydub moviepy Pillow

# 5. Fix ImageMagick policy (moviepy needs this)
echo ""
echo "🔧 Fixing ImageMagick policy..."
POLICY_FILE="/etc/ImageMagick-7/policy.xml"
if [ ! -f "$POLICY_FILE" ]; then
    POLICY_FILE="/etc/ImageMagick-6/policy.xml"
fi
if [ -f "$POLICY_FILE" ]; then
    sudo sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/g' "$POLICY_FILE" 2>/dev/null || true
    echo "   Fixed: $POLICY_FILE"
else
    echo "   ⚠️ No policy file found (might be fine)"
fi

echo ""
echo "============================================"
echo "  ✅ Setup complete!"
echo ""
echo "  To generate the video, run:"
echo "    cd ~/english-phrases-video"
echo "    source venv/bin/activate"
echo "    python generate.py"
echo "============================================"
