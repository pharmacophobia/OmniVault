#!/usr/bin/env bash
# OmniVault Self-Contained Desktop Installer
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🔐 Installing OmniVault Desktop Integration..."

# 1. Ensure scripts are executable
chmod +x "$DIR/run.sh" "$DIR/desktop/run.sh" "$DIR/desktop/main.py"

# 2. Register Desktop & Start Menu launchers
if [ -f "/home/k/.agents/skills/desktop-packager/scripts/create_launcher.py" ]; then
    python3 /home/k/.agents/skills/desktop-packager/scripts/create_launcher.py \
      --name "OmniVault" \
      --exec "$DIR/run.sh" \
      --icon "$DIR/assets/omnivault.png" \
      --comment "Zero-Knowledge AI-Augmented Cross-Platform Password Manager" \
      --categories "Utility;Security;" \
      --working-dir "$DIR/desktop" \
      --output-file "omnivault.desktop"
else
    # Fallback direct FreeDesktop entry
    MENU_DIR="$HOME/.local/share/applications"
    DESK_DIR="$HOME/Desktop"
    ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
    mkdir -p "$MENU_DIR" "$DESK_DIR" "$ICON_DIR"

    cp "$DIR/assets/omnivault.png" "$ICON_DIR/omnivault.png" 2>/dev/null || true

    cat <<EOF > "$MENU_DIR/omnivault.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=OmniVault
Comment=Zero-Knowledge AI-Augmented Cross-Platform Password Manager
Exec=$DIR/run.sh
Icon=$ICON_DIR/omnivault.png
Path=$DIR/desktop
Terminal=false
StartupNotify=true
Categories=Utility;Security;
EOF
    chmod +x "$MENU_DIR/omnivault.desktop"
    cp "$MENU_DIR/omnivault.desktop" "$DESK_DIR/omnivault.desktop"
    chmod +x "$DESK_DIR/omnivault.desktop"
fi

# 3. Trust desktop file (gio)
if command -v gio >/dev/null 2>&1; then
    gio set "$HOME/Desktop/omnivault.desktop" metadata::trusted true 2>/dev/null || true
fi

# 4. Update desktop entry cache
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo "✅ OmniVault successfully installed to Start Menu and Desktop!"
echo "   Launch directly from: $HOME/Desktop/omnivault.desktop or run: $DIR/run.sh"
