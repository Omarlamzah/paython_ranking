#!/bin/bash
# Run the search loop on a VPS. Logs to run_on_vps.log.
# If xvfb is installed, uses virtual display so Chrome runs like on a laptop (audio CAPTCHA solver can work).
# Otherwise runs Chrome headless (CAPTCHA often "bot detected" on headless).

cd "$(dirname "$0")"
SCRIPT="selenium_search_nextpitalipadress loop.py"
LOG="run_on_vps.log"
PY="${PYTHON:-.venv/bin/python}"

# Use virtual display when possible (no real DISPLAY) so Chrome runs non-headless = laptop-like, audio solver works
if [ -z "$DISPLAY" ] && command -v xvfb-run &>/dev/null; then
  exec xvfb-run -a "$0"
fi
# Only force headless when there is no display (and we're not under xvfb)
[ -z "$DISPLAY" ] && export RUN_HEADLESS=1

if [ ! -x "$PY" ]; then
  echo "Python not found at $PY. Use: PYTHON=/path/to/python ./run_on_vps.sh"
  exit 1
fi

echo "Started at $(date)" | tee -a "$LOG"
"$PY" "$SCRIPT" 2>&1 | tee -a "$LOG"
echo "Finished at $(date)" >> "$LOG"
