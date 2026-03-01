# Steps to run this project on your VPS (you are already logged in)

You are on: **Ubuntu VPS, root user**. Do the following in order.

---

## Step 1: Get the project onto the VPS

The project is on your **laptop**. Copy it to the VPS.

**On your laptop** (open a new terminal, don’t close the VPS session), run (replace `YOUR_VPS_IP` with the real IP, e.g. `123.45.67.89`):

```bash
cd /home/nextpital/Desktop/jball
scp -r GoogleRecaptchaBypass-main root@YOUR_VPS_IP:~
```

Enter the root password when asked. When it finishes, the folder `GoogleRecaptchaBypass-main` will be in `/root/` on the VPS.

**If you don’t have scp / prefer zip:** On the laptop, zip the folder, then:

```bash
scp GoogleRecaptchaBypass-main.zip root@YOUR_VPS_IP:~
```

Then on the VPS: `unzip GoogleRecaptchaBypass-main.zip`

---

## Step 2: On the VPS – install Chrome and dependencies

**On the VPS** (in your current SSH session):

```bash
cd ~/GoogleRecaptchaBypass-main
chmod +x setup_vps.sh
./setup_vps.sh
```

Wait until it finishes (Chrome + Python + ffmpeg installed).

---

## Step 3: On the VPS – create Python venv and install packages

Still on the VPS:

```bash
cd ~/GoogleRecaptchaBypass-main
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install selenium pproxy undetected-chromedriver pydub SpeechRecognition
```

---

## Step 4: On the VPS – turn on headless mode

Edit the script so it runs without a display:

```bash
sed -i 's/RUN_HEADLESS = False/RUN_HEADLESS = True/' "selenium_search_nextpitalipadress loop.py"
```

(Or edit the file and set `RUN_HEADLESS = True` yourself.)

---

## Step 5: On the VPS – run the script

```bash
cd ~/GoogleRecaptchaBypass-main
chmod +x run_on_vps.sh
./run_on_vps.sh
```

You should see logs like: `Loading Google...`, `Typing search query...`, `Clicked nextpital.com!`, etc.

To run in the background and keep logging to a file:

```bash
nohup ./run_on_vps.sh &
tail -f run_on_vps.log
```

(Press Ctrl+C to stop following the log; the script keeps running.)

---

## Quick reference (all on VPS after project is in `~/GoogleRecaptchaBypass-main`)

```bash
cd ~/GoogleRecaptchaBypass-main
./setup_vps.sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install selenium pproxy undetected-chromedriver pydub SpeechRecognition
sed -i 's/RUN_HEADLESS = False/RUN_HEADLESS = True/' "selenium_search_nextpitalipadress loop.py"
./run_on_vps.sh
```

---

## If something fails

- **Chrome not found:** run `which google-chrome` or `which chromium`. If missing, run `./setup_vps.sh` again or install manually (see VPS.md).
- **Permission denied:** you’re probably not in `~/GoogleRecaptchaBypass-main`. Run `cd ~/GoogleRecaptchaBypass-main` and try again.
- **No proxies:** ensure `proxies_maroc.txt` is in the same folder (it was copied with the project).
