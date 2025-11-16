#!/bin/bash
# Creates a desktop launcher for Notry

NOTRY_DIR="$1"

if [ -z "$NOTRY_DIR" ]; then
    NOTRY_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

NOTRY_DIR=$(cd "$NOTRY_DIR" && pwd)

cat > "$NOTRY_DIR/Notry.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Notry Notes
Comment=Terminal note-taking application
Exec=gnome-terminal -- bash -c "cd '$NOTRY_DIR' && ./notry; echo ''; read -p 'Press Enter to close...'"
Icon=utilities-terminal
Terminal=false
Categories=Utility;TextEditor;Office;
StartupNotify=true
Path=$NOTRY_DIR
EOF

chmod +x "$NOTRY_DIR/Notry.desktop"

echo "✅ Created: $NOTRY_DIR/Notry.desktop"
echo ""
echo "To use:"
echo "  1. Double-click Notry.desktop"
echo "  2. Or copy to desktop: cp Notry.desktop ~/Desktop/"
echo "  3. Or add to menu: cp Notry.desktop ~/.local/share/applications/"
