#!/bin/bash
# Run this ON THE VPS (Ubuntu/Debian) to install Chrome and dependencies so the search script
# works the same as on your laptop. Uses headless Chrome (no screen needed).
set -e

echo "=== Installing Chrome and dependencies on VPS (like your laptop) ==="

# Detect Debian/Ubuntu
if [ -f /etc/debian_version ]; then
  sudo apt-get update
  sudo apt-get install -y wget gnupg ca-certificates

  # Install Google Chrome (same browser as many laptops)
  if ! command -v google-chrome &>/dev/null; then
    echo "Installing Google Chrome..."
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-linux-signing-key.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-key.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
    sudo apt-get update
    sudo apt-get install -y google-chrome-stable
  else
    echo "Google Chrome already installed."
  fi

  # Fallback: Chromium if Chrome install fails (e.g. 32-bit or different arch)
  if ! command -v google-chrome &>/dev/null && ! command -v chromium-browser &>/dev/null && ! command -v chromium &>/dev/null; then
    echo "Installing Chromium instead..."
    sudo apt-get install -y chromium-browser || sudo apt-get install -y chromium
  fi

  # Python, venv, pip, ffmpeg (for audio captcha solver), xvfb (virtual display = laptop-like, audio solver works)
  echo "Installing Python, ffmpeg, xvfb..."
  sudo apt-get install -y python3 python3-venv python3-pip ffmpeg xvfb

  echo ""
  echo "Done. Chrome/Chromium and dependencies are installed."
  echo "Next: copy this project to the VPS, then run:"
  echo "  cd /path/to/paython_ranking"
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/pip install -r requirements.txt"
  echo "  .venv/bin/pip install selenium pproxy undetected-chromedriver pydub SpeechRecognition"
  echo "  chmod +x run_on_vps.sh && ./run_on_vps.sh"
  echo "  (xvfb is used automatically so Chrome runs like on your laptop and audio CAPTCHA can work)"
else
  echo "This script is for Debian/Ubuntu. On other distros install Chrome or Chromium and: python3, python3-venv, ffmpeg."
  exit 1
fi
