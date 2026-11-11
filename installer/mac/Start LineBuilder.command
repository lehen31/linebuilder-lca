#!/bin/bash
# Starts LineBuilder on this Mac and opens it in the browser. Closing this window stops it.
cd "$(dirname "$0")"
NAME="LineBuilder"
# 5050, not Flask's 5000: macOS uses port 5000 for AirPlay Receiver
PORT="${PORT:-5050}"
URL="http://127.0.0.1:$PORT"
export PORT
export PYTHONWARNINGS="ignore"

if [ ! -x .venv/bin/python ]; then
  echo "Run \"Install LineBuilder\" first."
  [ -t 0 ] && read -n 1 -s -r -p "Press any key"
  exit 1
fi
# an existing Activity Browser 2 project (brightway-folder.txt), else the own project in the subfolder "brightway":
# check that the chosen project is still there and still Brightway2
.venv/bin/python setup_ecoinvent.py --check || true
if [ ! -f linebuilder_config.json ]; then
  echo "$NAME needs ecoinvent 3.12 cutoff first."
  .venv/bin/python setup_ecoinvent.py
  if [ ! -f linebuilder_config.json ]; then
    echo
    echo "The Brightway project is not set up, so $NAME cannot start."
    [ -t 0 ] && read -n 1 -s -r -p "Press any key"
    exit 1
  fi
  echo
fi
if [ -f brightway-folder.txt ]; then
  BRIGHTWAY2_DIR="$(cat brightway-folder.txt)"
else
  BRIGHTWAY2_DIR="$PWD/brightway"
  mkdir -p "$BRIGHTWAY2_DIR"   # legacy bw2data stops if this folder does not exist
fi
export BRIGHTWAY2_DIR
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use ($NAME may already be running): $URL"
  open "$URL"
  exit 0
fi

echo "$NAME: $URL"
echo "Brightway: $BRIGHTWAY2_DIR, project \"$(.venv/bin/python -c 'import json; print(json.load(open("linebuilder_config.json"))["project"])')\""
echo "Keep this window open. Closing it stops $NAME."
echo "The first calculation reads ecoinvent and takes a minute."
( sleep 3; open "$URL" ) &
exec .venv/bin/python app.py
