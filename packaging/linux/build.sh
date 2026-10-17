#!/bin/bash
# Build the Linux packages: a .deb, an AppImage and a .tar.gz  (run from anywhere; output goes to ./dist-packages)
#   packaging/linux/build.sh [version]
# Needs: python3-venv, dpkg-deb, and internet the first time (pip packages, appimagetool).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${1:-$(cat "$ROOT/VERSION")}"
OUT="$ROOT/dist-packages"
WORK="$ROOT/build-linux"
rm -rf "$WORK" && mkdir -p "$WORK" "$OUT"

echo "== 1/4  build environment"
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install -q --upgrade pip
"$WORK/venv/bin/pip" install -q -r "$ROOT/requirements.txt" pyinstaller
"$WORK/venv/bin/python" "$ROOT/packaging/make_icon.py"
"$WORK/venv/bin/python" "$ROOT/packaging/fetch_models.py"

echo "== 2/4  bundle the program"
(cd "$WORK" && "$WORK/venv/bin/pyinstaller" "$ROOT/packaging/recall-session.spec" --noconfirm \
    --distpath "$WORK/dist" --workpath "$WORK/pyi" >"$WORK/pyinstaller.log" 2>&1)
APP="$WORK/dist/recall-session"
"$APP/recall-session" --self-test | tail -1

DESKTOP='[Desktop Entry]
Type=Application
Name=Recall-Session
Comment=Record classes and videos, get live transcripts and notes
Exec=recall-session
Icon=recall-session
Categories=Education;AudioVideo;
Terminal=false
StartupWMClass=Recall-Session'

echo "== 3/4  .deb"
DEB="$WORK/deb"
mkdir -p "$DEB/opt" "$DEB/usr/bin" "$DEB/usr/share/applications" "$DEB/usr/share/icons/hicolor/256x256/apps" "$DEB/DEBIAN"
cp -a "$APP" "$DEB/opt/recall-session"
ln -s /opt/recall-session/recall-session "$DEB/usr/bin/recall-session"
echo "$DESKTOP" > "$DEB/usr/share/applications/recall-session.desktop"
cp "$ROOT/assets/icon.png" "$DEB/usr/share/icons/hicolor/256x256/apps/recall-session.png"
cat > "$DEB/DEBIAN/control" <<EOF
Package: recall-session
Version: $VERSION
Section: education
Priority: optional
Architecture: amd64
Depends: ffmpeg, gnome-screenshot, pipewire-bin
Recommends: pipewire-pulse
Installed-Size: $(du -sk "$DEB/opt" | cut -f1)
Maintainer: Jibach Yadav <jibachh202@gmail.com>
Homepage: https://github.com/jibachyadav/Recall-Session
Description: Record classes and videos, with live transcripts and notes
 Recall-Session listens to online classes and videos, keeps a live transcript,
 flags confusing moments and writes summaries. Speech recognition runs locally.
EOF
chmod -R u+rwX,go+rX,go-w "$DEB"
dpkg-deb --root-owner-group --build "$DEB" "$OUT/recall-session_amd64.deb" >/dev/null

echo "== 4/4  AppImage and .tar.gz"
AD="$WORK/AppDir"
mkdir -p "$AD/usr/bin"
cp -a "$APP/." "$AD/usr/bin/"
cp "$ROOT/assets/icon.png" "$AD/recall-session.png"
echo "$DESKTOP" | sed 's/^Exec=.*/Exec=recall-session/' > "$AD/recall-session.desktop"
printf '#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/usr/bin/recall-session" "$@"\n' > "$AD/AppRun"
chmod +x "$AD/AppRun"
TOOL="$HOME/.cache/recall-session-build/appimagetool"
if [ ! -x "$TOOL" ]; then
    mkdir -p "$(dirname "$TOOL")"
    curl -sL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$AD" "$OUT/Recall-Session-x86_64.AppImage" >"$WORK/appimage.log" 2>&1 \
    || { echo "AppImage step failed:"; tail -5 "$WORK/appimage.log"; }
tar -C "$WORK/dist" -czf "$OUT/recall-session-linux-x86_64.tar.gz" recall-session

echo; ls -lh "$OUT"
