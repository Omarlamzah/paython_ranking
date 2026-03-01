#!/bin/bash
# Run the search loop on a VPS (no display). Logs to run_on_vps.log.
# 1. In selenium_search_nextpitalipadress loop.py set: RUN_HEADLESS = True
# 2. Install on VPS: Chrome (or Chromium), Python 3, pip, ffmpeg; create venv and install deps.
# 3. Run: ./run_on_vps.sh   or: nohup ./run_on_vps.sh &   (keeps running after you disconnect)

cd "$(dirname "$0")"
SCRIPT="selenium_search_nextpitalipadress loop.py"
LOG="run_on_vps.log"
PY="${PYTHON:-.venv/bin/python}"

if [ ! -x "$PY" ]; then
  echo "Python not found at $PY. Use: PYTHON=/path/to/python ./run_on_vps.sh"
  exit 1
fi

echo "Started at $(date)" | tee -a "$LOG"
"$PY" "$SCRIPT" 2>&1 | tee -a "$LOG"
echo "Finished at $(date)" >> "$LOG"
