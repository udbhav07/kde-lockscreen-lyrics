#!/usr/bin/env bash
# Copies this project's lock screen UI into KDE's system folder.
set -euo pipefail

KDE_DIR=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen

cd "$(dirname "$0")"

echo "Installing lock screen UI into $KDE_DIR (needs sudo)..."
sudo cp -r lockscreen/. "$KDE_DIR/"

echo "Done. Test it with: /usr/libexec/kscreenlocker_greet --testing"

