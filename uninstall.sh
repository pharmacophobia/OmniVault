#!/usr/bin/env bash
# OmniVault Desktop Uninstaller
set -e

echo "🗑️ Removing OmniVault Desktop Integration..."

rm -f "$HOME/.local/share/applications/omnivault.desktop"
rm -f "$HOME/Desktop/omnivault.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/omnivault.png"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo "✅ OmniVault desktop shortcuts removed cleanly."
