# Run this project automatically on a VPS

---

## How it works: laptop (with GUI) vs VPS (only terminal)

**On your laptop (has a screen):**
- You run the script → Chrome **opens a window** you can see.
- The script tells Chrome: “go to Google, type this, click that.”
- You **see** the browser doing it (page loads, search box, results, click on nextpital).
- Same script, same actions. You watch it on the screen.

**On the VPS (no screen, only terminal):**
- There is **no monitor and no desktop** — nothing to show a window.
- Chrome is still installed. The script runs the **exact same steps**: go to Google, type search, click nextpital.
- Chrome runs in **“headless” mode**: it does all the same work (load pages, click, type) but **does not draw any window** because there is no screen. It’s the same program, just “no display.”
- You don’t see a browser. You only see **text in the terminal**: “Loading Google…”, “Clicked nextpital.com!”, etc. That’s how you know it worked.

So:
- **Laptop:** Chrome window visible → script controls it → you see it.
- **VPS:** Chrome runs “in the background” (headless) → script controls it the same way → you see only the **log in the terminal** (and in `run_on_vps.log` if you use the script).

The **search and click logic is identical**; the only difference is whether a window is shown (laptop) or not (VPS).

---

## 1. On the VPS: install Chrome and dependencies (so it works like your laptop)

## 1. On the VPS: install Chrome and dependencies (so it works like your laptop)

**Option A – Use the setup script (easiest, Ubuntu/Debian):**

Copy the project to the VPS, then run on the VPS:

```bash
chmod +x setup_vps.sh
./setup_vps.sh
```

This installs **Google Chrome** (or Chromium), Python 3, venv, and ffmpeg so the search runs the same as on your laptop.

**Option B – Install by hand (Ubuntu/Debian):**

```bash
sudo apt-get update
sudo apt-get install -y wget gnupg
# Google Chrome (same as many laptops)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-linux-signing-key.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-key.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update && sudo apt-get install -y google-chrome-stable
# Python and ffmpeg
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg
```

---

## 2. Enable headless mode (no window on VPS)

In `selenium_search_nextpitalipadress loop.py` set:

```python
RUN_HEADLESS = True
```

---

## 3. Project and venv on VPS

After Chrome is installed (step 1), set up the project:

```bash
# Copy project to VPS (scp, rsync, or git clone), then:
cd /path/to/GoogleRecaptchaBypass-main
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install selenium pproxy undetected-chromedriver pydub SpeechRecognition
chmod +x run_on_vps.sh
```

---

## 4. Run automatically

**Option A – Run once in background (survives disconnect):**

```bash
nohup ./run_on_vps.sh &
# Output in run_on_vps.log; check with: tail -f run_on_vps.log
```

**Option B – Run every day at 8:00 (cron):**

```bash
crontab -e
# Add line (adjust path):
0 8 * * * cd /path/to/GoogleRecaptchaBypass-main && ./run_on_vps.sh >> run_on_vps.log 2>&1
```

**Option C – Run as a systemd service (restart on failure):**

Create `/etc/systemd/system/nextpital-search.service`:

```ini
[Unit]
Description=Nextpital Google search loop
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/GoogleRecaptchaBypass-main
ExecStart=/path/to/GoogleRecaptchaBypass-main/.venv/bin/python "selenium_search_nextpitalipadress loop.py"
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nextpital-search
sudo systemctl start nextpital-search
sudo journalctl -u nextpital-search -f
```

## 5. Files to have on VPS

- `selenium_search_nextpitalipadress loop.py` (with `RUN_HEADLESS = True`)
- `RecaptchaSolverSelenium.py`
- `proxies_maroc.txt` (or your proxy file)
- `.venv` with dependencies

Optional: `.2captcha_key` if you use 2Captcha.

## Notes

- **VPS has no Chrome by default** — run `setup_vps.sh` (or install Chrome/Chromium manually) so the script can do the same search as on your laptop.
- Headless Chrome may be detected more often by Google; rotating proxies (e.g. Morocco list) help.
- For cron, the script runs once per cron trigger; `NUM_LOOPS` controls how many searches per run.
- To run every 6 hours: `0 */6 * * * cd /path/to/GoogleRecaptchaBypass-main && ./run_on_vps.sh >> run_on_vps.log 2>&1`
