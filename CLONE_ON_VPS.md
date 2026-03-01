# Download and run the project on the VPS (from GitHub)

Run these commands **on the VPS** in order.

---

## 1. Install git (if not already)

```bash
apt-get update && apt-get install -y git
```

---

## 2. Clone the project from GitHub

```bash
cd /root
git clone https://github.com/Omarlamzah/paython_ranking.git
cd paython_ranking
ls
```

You should see the project files (e.g. `selenium_search_nextpitalipadress loop.py`, `setup_vps.sh`, etc.).

---

## 3. Install Chrome and dependencies

```bash
chmod +x setup_vps.sh
./setup_vps.sh
```

---

## 4. Create Python venv and install packages

**Option A – Use full path to Python (fixes "Unable to determine path" on some VPS):**

```bash
rm -rf .venv
/usr/bin/python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install selenium pproxy undetected-chromedriver pydub SpeechRecognition
```

**Option B – If venv still fails, install without venv (use system Python):**

```bash
pip3 install --user -r requirements.txt
pip3 install --user selenium pproxy undetected-chromedriver pydub SpeechRecognition
```

Then run the script with: `PYTHON=python3 ./run_on_vps.sh`

**Before first run:** `chmod +x run_on_vps.sh` (fixes "Permission denied").

---

## reCAPTCHA on VPS: "Try again later (bot detected)"

On a headless VPS, Google often blocks the **audio** challenge and shows "Try again later". The **reliable fix** is to use **2Captcha** (paid API) so the script can get a token even when the audio path is blocked.

**On the VPS**, create the API key file (use your real 2Captcha key from https://2captcha.com):

```bash
cd ~/paython_ranking
echo "YOUR_2CAPTCHA_API_KEY" > .2captcha_key
chmod 600 .2captcha_key
```

Then run `./run_on_vps.sh` again. When the audio solver fails, the script will try 2Captcha and inject the token. Without a key, the script can only wait and retry (often still "Try again later" on headless).

---

## 5. Enable headless mode

```bash
sed -i 's/RUN_HEADLESS = False/RUN_HEADLESS = True/' "selenium_search_nextpitalipadress loop.py"
```

---

## 6. Add your proxy file (not in GitHub for security)

Create your proxy list on the VPS. Example for Morocco (edit with your real credentials):

```bash
nano proxies_maroc.txt
```

Paste one proxy per line, e.g.:
```
socks5://YOUR_USER:sgtmg56wzp7i@p.webshare.io:80
```
Save (Ctrl+O, Enter, Ctrl+X). Or copy the file from your laptop with scp. Use **http://** (not socks5) for Webshare backbone proxies.

---

## 7. If you see "Chrome instance exited" or "session not created"

Chrome headless often needs extra libraries on the VPS. Install them:

```bash
apt-get update
apt-get install -y libgbm1 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libasound2
```

If Chrome still exits, try Chromium instead:

```bash
apt-get install -y chromium-browser
# Or on some systems:
apt-get install -y chromium
```

Then run the script again.

---

## 8. Run the script

```bash
chmod +x run_on_vps.sh
./run_on_vps.sh
```

To run in background: `nohup ./run_on_vps.sh &` then `tail -f run_on_vps.log`
