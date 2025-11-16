#!/bin/bash
# Notry Installation Script

echo "Notry Setup"
echo "==========="
echo ""

# Check Python version
if ! command -v python3.14 &> /dev/null; then
    echo "⚠️  Python 3.14 not found"
    echo ""
    echo "Notry is configured to use Python 3.14."
    echo "Install Python 3.14 or edit the 'notry' file to use your Python version."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "✓ Found Python 3.14"

# Check if textual is installed
if python3.14 -c "import textual" 2>/dev/null; then
    echo "✓ Textual already installed"
    echo ""
    echo "You're ready! Run: ./notry"
    exit 0
fi

echo ""
echo "Installing textual library..."

# Try to install
python3.14 -m pip install --user textual 2>/dev/null || \
python3.14 -m pip install --user --break-system-packages textual

# Verify
if python3.14 -c "import textual" 2>/dev/null; then
    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "Run: ./notry"
else
    echo ""
    echo "❌ Installation failed"
    echo ""
    echo "Try manually:"
    echo "  python3.14 -m pip install --user --break-system-packages textual"
fi
