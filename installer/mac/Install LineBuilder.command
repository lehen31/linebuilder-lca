#!/bin/bash
# Installs LineBuilder into this folder: its own Python 3.11, legacy Brightway2 and the app, then builds its
# Brightway project from your ecoinvent 3.12 cutoff. Needs internet once, no admin password. Nothing outside this
# folder is changed except the app "LineBuilder" on the desktop, which starts it (no PATH, no shell profile, no conda,
# and the Brightway data stay in this folder: the Activity Browser and its projects are not touched).
set -euo pipefail
cd "$(dirname "$0")"
DIR="$PWD"
NAME="LineBuilder"
UV_VERSION="0.9.5"
export UV_PYTHON_INSTALL_DIR="$DIR/.tools/python"   # Python stays inside this folder
export UV_CACHE_DIR="$DIR/.tools/cache"
export UV_PYTHON_PREFERENCE=only-managed           # never use another Python of this Mac (conda, Homebrew)
export BRIGHTWAY2_DIR="$DIR/brightway"             # Brightway projects of LineBuilder only
mkdir -p "$BRIGHTWAY2_DIR" 2>/dev/null || true     # legacy bw2data stops if this folder does not exist

pause() { if [ -t 0 ]; then echo; read -n 1 -s -r -p "Press any key to close"; echo; fi; }
fail() { echo; echo "ERROR: $1"; echo "Log: $DIR/installation-log.txt"; pause; exit 1; }
trap 'fail "Installation stopped (line $LINENO). Check the internet connection and run it again."' ERR

mkdir -p "$DIR/.tools" 2>/dev/null && touch "$DIR/.tools/.write-test" 2>/dev/null && rm -f "$DIR/.tools/.write-test" \
  || { echo "ERROR: no write access to $DIR"
       echo "Move the folder to Documents, or allow Terminal access (System Settings → Privacy & Security → Files and Folders)."
       pause; exit 1; }
exec > >(tee "$DIR/installation-log.txt") 2>&1

echo "$NAME: installation"
echo "Folder: $DIR"
echo "macOS $(sw_vers -productVersion), $(uname -m)"
echo

UV="$DIR/.tools/uv"
if [ ! -x "$UV" ]; then
  echo "1/4  Loading the installer tool uv $UV_VERSION …"
  # The release archive straight from GitHub, checked against a pinned checksum. No install script.
  case "$(uname -m)" in
    arm64) UV_ARCH=aarch64-apple-darwin; UV_SHA=dc098ff224d78ed418e121fd374f655949d2c7031a70f6f6604eaf016a130433 ;;
    *)     UV_ARCH=x86_64-apple-darwin;  UV_SHA=58b1d4a25aa8ff99147c2550b33dcf730207fe7e0f9a0d5d36a1bbf36b845aca ;;
  esac
  TGZ="$DIR/.tools/uv.tar.gz"
  curl -LfsS --retry 3 --connect-timeout 20 -o "$TGZ" "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$UV_ARCH.tar.gz" \
    || fail "Download of uv failed (github.com). Check the internet connection and run it again."
  [ "$(shasum -a 256 "$TGZ" | cut -d' ' -f1)" = "$UV_SHA" ] || fail "uv download corrupted, run it again."
  tar -xzf "$TGZ" -C "$DIR/.tools" --strip-components 1
  rm -f "$TGZ"
  [ -x "$UV" ] || fail "uv not found."
fi

echo "2/4  Loading Python 3.11 …"
"$UV" venv --quiet --allow-existing --python 3.11 "$DIR/.venv"

echo "3/4  Loading Brightway2 and the app, this takes a few minutes …"
# requirements-lock.txt holds the SHA-256 checksum of every package file: uv installs a file only when it matches.
# A mismatch stops the installation; only versions that do not fit this Mac fall back to the newest matching ones
# (requirements-app.txt, without checksums).
ERRS="$DIR/.tools/lock-errors.txt"
if ! "$UV" pip install --quiet --require-hashes --python "$DIR/.venv/bin/python" -r requirements-lock.txt 2> "$ERRS"; then
  cat "$ERRS"
  if grep -qi "hash mismatch" "$ERRS"; then
    fail "A downloaded package does not match its checksum, so it was not installed. Run the installation again later; if it happens again, send installation-log.txt."
  fi
  echo "     The tested versions do not fit this Mac, using the newest matching ones (without checksums) …"
  "$UV" pip install --quiet --python "$DIR/.venv/bin/python" -r requirements-app.txt
fi
rm -f "$ERRS"
"$DIR/.venv/bin/python" -c "import brightway2, bw2io, flask, yaml, xlsxwriter, py7zr" >/dev/null 2>&1 || fail "Installation check failed."
rm -rf "$DIR/.tools/cache"  # downloads only

trap - ERR

# "LineBuilder.app", here and on the desktop: it opens "Start LineBuilder" of this folder
make_app() {
  local APP="$1/$NAME.app"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" || return 1
  [ -f "$DIR/AppIcon.icns" ] && cp "$DIR/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
  cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>$NAME</string>
  <key>CFBundleDisplayName</key><string>$NAME</string>
  <key>CFBundleIdentifier</key><string>io.github.lehen31.linebuilder</string>
  <key>CFBundleExecutable</key><string>$NAME</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSUIElement</key><true/>
</dict></plist>
PLIST
  cat > "$APP/Contents/MacOS/$NAME" <<LAUNCH
#!/bin/bash
# Starts $NAME from its folder (written by the installer).
START="$DIR/Start LineBuilder.command"
if [ ! -f "\$START" ]; then
  osascript -e 'display alert "$NAME" message "The $NAME folder has moved. Run \"Install LineBuilder\" in its new place again."'
  exit 1
fi
open "\$START"
LAUNCH
  chmod +x "$APP/Contents/MacOS/$NAME"
  touch "$APP"
}
make_app "$DIR" || true
if make_app "$HOME/Desktop" 2>/dev/null; then
  echo "The app \"$NAME\" is on the desktop (and in this folder): double-click it to start."
else
  echo "Start $NAME with \"$NAME\" in this folder (no access to the desktop)."
fi

echo
if [ -f linebuilder_config.json ]; then
  echo "4/4  The Brightway project is already set up."
else
  echo "4/4  Setting up the Brightway project with ecoinvent 3.12 cutoff: from its download (.7z or folder),"
  echo "     or an existing Activity Browser 2 project that has it (licensed, not included)."
  "$DIR/.venv/bin/python" setup_ecoinvent.py || true
  if [ -f linebuilder_config.json ]; then
    echo "     Brightway project ready."
  else
    echo "     The Brightway project is not set up yet. \"Start LineBuilder\" asks for ecoinvent again."
  fi
fi

echo
echo "Done. Start $NAME with the app \"$NAME\" on the desktop, or \"Start LineBuilder\" in this folder."
pause
