#!/bin/zsh
# Packs LineBuilder for people who do not use conda or Brightway themselves:
#   installer/dist/LineBuilder-Mac.zip and installer/dist/LineBuilder-Windows.zip
# Each holds the app as committed (default HEAD), the install and start scripts, setup_ecoinvent.py, the
# requirements with checksums and the instructions. No ecoinvent, no venv. See installer/README.md.
#   installer/pack.sh            from HEAD
#   installer/pack.sh <ref>      from another commit, tag or branch
#   installer/pack.sh --lock     only renews common/requirements-lock.txt from common/requirements-app.txt (needs uv)
# Windows needs CRLF in .cmd/.ps1/.txt and a UTF-8 BOM in install.ps1 (else PowerShell 5.1 reads non-ASCII as ANSI).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(git rev-parse --show-toplevel)"

if [ "${1:-}" = "--lock" ]; then
  uv pip compile --quiet --universal --python-version 3.11 --generate-hashes --no-header \
    --custom-compile-command "installer/pack.sh --lock" common/requirements-app.txt -o common/requirements-lock.txt
  echo "installer/common/requirements-lock.txt renewed"
  exit 0
fi

REF="${1:-HEAD}"
COMMIT="$(git rev-parse --short "$REF") $(git log -1 --format=%cs "$REF")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p dist
for OS in mac windows; do
  case $OS in mac) SUF=Mac ;; windows) SUF=Windows ;; esac
  OUT="$TMP/$OS/LineBuilder"
  ZIP="dist/LineBuilder-$SUF.zip"
  rm -f "$ZIP"
  mkdir -p "$OUT"
  # the app: code, process library, bundled foreground data, setup, licence
  git -C "$ROOT" archive "$REF" app.py linebuilder_core.py process_templates.yaml setup_project.py data LICENSE README.md \
    | tar -x -C "$OUT"
  mv "$OUT/README.md" "$OUT/README-developers.md"
  git -C "$ROOT" archive "$REF" installer/common "installer/$OS" | tar -x -C "$TMP"
  mv "$TMP/installer/common"/* "$TMP/installer/$OS"/* "$OUT/"
  rm -rf "$TMP/installer"
  echo "linebuilder-lca $COMMIT" > "$OUT/VERSION"
  if [ $OS = mac ]; then
    chmod +x "$OUT"/*.command
    ditto -c -k --norsrc --noextattr --keepParent "$OUT" "$ZIP"
  else
    for f in "$OUT"/*.cmd "$OUT"/*.ps1 "$OUT"/*.txt; do perl -pi -e 's/\r?\n/\r\n/' "$f"; done
    printf '\xef\xbb\xbf' | cat - "$OUT/install.ps1" > "$OUT/install.ps1.bom" && mv "$OUT/install.ps1.bom" "$OUT/install.ps1"
    (cd "$TMP/$OS" && zip -qrX "$OLDPWD/$ZIP" LineBuilder)
  fi
  echo "installer/$ZIP ($(du -h "$ZIP" | cut -f1)) from linebuilder-lca $COMMIT"
done
