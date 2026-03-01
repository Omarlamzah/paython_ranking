"""
Selenium script: loop N times, each time search a keyword on Google,
find Nextpital and click it. Each run can use a different proxy (IP).

- Search: Google only. If Google shows CAPTCHA, script tries audio solver then 2Captcha then waits.
- Proxies: put in proxies.txt or proxies_maroc.txt (http:// or socks5:// USER:PASS@HOST:PORT).
- For proxies with auth we run pproxy as local proxy so Chrome sees no login dialog.

Requirements:
  pip install selenium pproxy undetected-chromedriver
  For audio reCAPTCHA solver (optional): pip install pydub SpeechRecognition — and install ffmpeg.
  Chrome browser must be installed.

--- Run automatically on a VPS (no screen) ---
  1. In this file set: RUN_HEADLESS = True
  2. On the VPS install Chrome, Python 3, venv, ffmpeg; copy this project and create venv + install deps.
  3. Run in background: nohup ./run_on_vps.sh &   (or use cron / systemd — see VPS.md)

--- If CAPTCHA keeps appearing (from web research) ---
Google flags: same device fingerprint, automation signals (Selenium), and sometimes IP.
We already: rotate proxies, fresh Chrome profile per run, varied window/fingerprint, human delays.
Further options:
  1) Solve manually: when the script says "Solve it in the browser...", solve and press Enter.
  2) CAPTCHA solver APIs: 2Captcha, CapSolver, Anti-Captcha can solve reCAPTCHA for a fee
     (you'd need to integrate their API when CAPTCHA is detected).
  3) Try Playwright instead of Selenium: often less detected (pip install playwright playwright-stealth).
  4) Use a "Web Unblocker" / scraping API (e.g. Oxylabs) that handles blocks for you.
"""

import os
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Config ---
NUM_LOOPS = 10
KEYWORD = "Logiciel pour médecins · Maroc"
PROXY_FILE = "proxies_maroc.txt"
# For Morocco (Maroc) only: in Webshare dashboard allocate proxies to country MA, then
# put Morocco proxy lines in proxies_maroc.txt and set PROXY_FILE = "proxies_maroc.txt"
# Faster navigation: shorter delays (less human-like, may trigger more CAPTCHAs). Set False to be safer.
FASTER_NAVIGATION = True
# Run Chrome headless (no window). Use True on VPS/servers without a display.
RUN_HEADLESS = False
# Search: Google only
SEARCH_ENGINE = "google"
# Use standard Chrome only (undetected_chromedriver often fails with proxy: "cannot connect to chrome at 127.0.0.1")
USE_STANDARD_CHROME = True
# Use TLS to connect to proxy (http+ssl). Set False if you get ERR_SSL_PROTOCOL_ERROR (e.g. gate.decodo.com)
USE_HTTPS_PROXY_UPSTREAM = False
# If no proxies in file, fetch real proxy IPs from a free list (optional; quality varies)
FETCH_FREE_PROXIES = False
FREE_PROXY_COUNT = 10
# 2Captcha API key: set CAPTCHA_2CAPTCHA_KEY env var, or put key in .2captcha_key in this folder (no quotes)
# Get key at https://2captcha.com/enterpage — then: export CAPTCHA_2CAPTCHA_KEY=your_key
CAPTCHA_2CAPTCHA_KEY = os.environ.get("CAPTCHA_2CAPTCHA_KEY", "").strip()
if not CAPTCHA_2CAPTCHA_KEY:
    _key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".2captcha_key")
    if os.path.isfile(_key_path):
        with open(_key_path, "r") as _f:
            CAPTCHA_2CAPTCHA_KEY = _f.read().strip()

# Audio reCAPTCHA solver (same approach as RecaptchaSolver: audio challenge + speech recognition)
# Requires: pydub, SpeechRecognition, ffmpeg. Install with: pip install pydub SpeechRecognition
try:
    from RecaptchaSolverSelenium import RecaptchaSolverSelenium
    AUDIO_CAPTCHA_AVAILABLE = True
except ImportError:
    RecaptchaSolverSelenium = None
    AUDIO_CAPTCHA_AVAILABLE = False


def _log(msg):
    print(msg, flush=True)


def load_proxies():
    """Load proxy list from PROXY_FILE or return empty list."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), PROXY_FILE)
    if not os.path.isfile(path):
        return []
    proxies = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if not line.startswith("http") and not line.startswith("socks5"):
                    line = "http://" + line
                proxies.append(line)
    return proxies


def fetch_free_proxies(count=10):
    """Fetch real proxy IP:port from a free public list. Quality/speed varies."""
    # ProxyScrape and similar APIs return ip:port per line
    urls = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    ]
    seen = set()
    out = []
    for url in urls:
        if len(out) >= count:
            break
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                for line in r.read().decode("utf-8", errors="ignore").strip().splitlines():
                    line = line.strip()
                    if not line or not re.match(r"^[\d.]+\s*:\s*\d+", line.replace(" ", "")):
                        continue
                    # normalize to ip:port
                    if " " in line:
                        line = line.split()[0]
                    line = line.replace(" ", "")
                    if "://" not in line:
                        line = "http://" + line
                    if line not in seen:
                        seen.add(line)
                        out.append(line)
                        if len(out) >= count:
                            break
        except Exception as e:
            _log("Free proxy fetch failed (%s): %s" % (url[:40], e))
    return out


# --- Local proxy via pproxy (handles upstream auth so Chrome sees no login dialog) ---
def _proxy_url_for_pproxy(proxy_url):
    """Convert http(s)/socks5 proxy URL to pproxy remote URI. pproxy supports http, http+ssl, socks5."""
    host_port, username, password = _parse_proxy(proxy_url)
    if not host_port or not username or not password:
        return None
    raw = (proxy_url or "").strip().lower()
    if raw.startswith("socks5://"):
        return "socks5://%s#%s:%s" % (host_port, username, password)
    if USE_HTTPS_PROXY_UPSTREAM and raw.startswith("https://"):
        scheme = "http+ssl"
    else:
        scheme = "http"
    return "%s://%s#%s:%s" % (scheme, host_port, username, password)


def _start_pproxy(proxy_url):
    """Start pproxy: local no-auth proxy -> upstream proxy with auth. Returns (subprocess.Popen, port) or (None, None)."""
    pproxy_remote = _proxy_url_for_pproxy(proxy_url)
    if not pproxy_remote:
        _log("pproxy: could not parse proxy URL (use http:// or socks5://user:pass@host:port)")
        return None, None
    # Use a random port to avoid "address already in use" from previous run
    port = random.randint(20000, 55000)
    try:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "pproxy",
                "-l", "http://127.0.0.1:%s" % port,
                "-r", pproxy_remote,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        time.sleep(2.5)
        if proc.poll() is not None:
            _, err = proc.communicate(timeout=1)
            err = (err or b"").decode("utf-8", errors="replace").strip() or "unknown"
            _log("pproxy exited: %s" % err[:200])
            return None, None
        return proc, port
    except Exception as e:
        _log("pproxy start failed: %s" % e)
        return None, None


def _stop_pproxy(proc):
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _parse_proxy(proxy_url):
    """Return (host_port, username, password). Supports http://, https://, socks5:// user:pass@host:port."""
    if not proxy_url:
        return None, None, None
    u = proxy_url.strip()
    if u.startswith("http://"):
        u = u[7:]
    elif u.startswith("https://"):
        u = u[8:]
    elif u.startswith("socks5://"):
        u = u[9:]
    if "@" in u:
        auth, host_port = u.rsplit("@", 1)
        if ":" in auth:
            username, password = auth.split(":", 1)
            return host_port.strip(), username.strip(), password.strip()
        return host_port.strip(), auth.strip(), None
    return u.strip(), None, None


def _apply_stealth_cdp(driver):
    """Reduce automation detection; vary fingerprint slightly per run (same laptop looks less identical)."""
    try:
        cores = random.choice([4, 6, 8, 12])
        mem = random.choice([4, 8, 16])
        script = """
        Object.defineProperty(navigator, 'webdriver', { get: function() { return undefined; } });
        window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
        Object.defineProperty(navigator, 'plugins', {
            get: function() {
                var p = [1, 2, 3, 4, 5];
                p.item = function(i) { return p[i] || null; };
                p.namedItem = function() { return null; };
                p.refresh = function() {};
                return p;
            }
        });
        Object.defineProperty(navigator, 'languages', { get: function() { return ['en-US', 'en']; } });
        Object.defineProperty(navigator, 'platform', { get: function() { return 'Linux x86_64'; } });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: function() { return %d; } });
        Object.defineProperty(navigator, 'deviceMemory', { get: function() { return %d; } });
        Object.defineProperty(navigator, 'maxTouchPoints', { get: function() { return 0; } });
        """ % (cores, mem)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
    except Exception as e:
        _log("Stealth CDP (optional): %s" % e)


def _build_chrome_options(proxy=None, pproxy_port=None, add_stealth_options=True, user_data_dir=None):
    """Build ChromeOptions. user_data_dir = fresh profile per run (no cookies/history, less "same device" detection)."""
    options = webdriver.ChromeOptions()
    if user_data_dir:
        options.add_argument("--user-data-dir=%s" % user_data_dir)
    if add_stealth_options:
        try:
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
        except Exception:
            pass
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    if add_stealth_options:
        options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-background-networking")
    if RUN_HEADLESS:
        options.add_argument("--headless=new")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        w, h = 1920, 1080
    else:
        w, h = 1920 + random.randint(-30, 30), 1080 + random.randint(-20, 20)
    options.add_argument("--window-size=%d,%d" % (w, h))
    if not RUN_HEADLESS:
        options.add_argument("--start-maximized")
    if proxy:
        host_port, username, password = _parse_proxy(proxy)
        if host_port:
            if username and password and pproxy_port:
                options.add_argument("--proxy-server=127.0.0.1:%s" % pproxy_port)
                _log("Using proxy: %s (via pproxy on port %s)" % (host_port, pproxy_port))
            elif username and password:
                pproxy_proc, local_port = _start_pproxy(proxy)
                if pproxy_proc and local_port:
                    options.add_argument("--proxy-server=127.0.0.1:%s" % local_port)
                    _log("Using proxy: %s (via pproxy on port %s)" % (host_port, local_port))
                else:
                    _log("pproxy failed, running without proxy for this run.")
            else:
                options.add_argument("--proxy-server=http://%s" % host_port)
                _log("Using proxy: %s" % host_port)
    else:
        options.add_argument("--disable-extensions")
    return options


def create_chrome_driver(proxy=None):
    """Returns (driver, pproxy_process or None). Call _stop_pproxy(pproxy_process) when done."""
    _log("Preparing Chrome...")
    use_uc = not USE_STANDARD_CHROME and (SEARCH_ENGINE or "").strip().lower() == "google"
    pproxy_proc, pproxy_port = None, None
    if proxy:
        host_port, username, password = _parse_proxy(proxy)
        if host_port and username and password:
            pproxy_proc, pproxy_port = _start_pproxy(proxy)
    # Fresh profile per run: no cookies, no history — each run looks like a new device/session
    user_data_dir = tempfile.mkdtemp(prefix="chrome_run_")
    options_fallback = _build_chrome_options(proxy=proxy, pproxy_port=pproxy_port, add_stealth_options=False, user_data_dir=user_data_dir)
    if use_uc:
        try:
            # Minimal options only (no excludeSwitches) so UC works on Chrome builds that reject them
            import undetected_chromedriver as uc
            driver = uc.Chrome(options=options_fallback)
            _apply_stealth_cdp(driver)
            _log("Chrome started (undetected mode for Google).")
        except Exception as e:
            err_msg = (str(e).split("\n")[0] or str(e))[:80]
            _log("undetected_chromedriver failed (%s), using standard Chrome." % err_msg)
            driver = webdriver.Chrome(options=options_fallback)
            _apply_stealth_cdp(driver)
            _log("Chrome started.")
    else:
        driver = webdriver.Chrome(options=options_fallback)
        _apply_stealth_cdp(driver)
        _log("Chrome started.")
    return driver, pproxy_proc


def log_ip_used(driver):
    """Fetch and log the public IP address used by this browser session (proxy or not)."""
    for url in ("https://icanhazip.com",):
        try:
            driver.get(url)
            ip = WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            ).text.strip().split("\n")[0].strip()
            if ip and re.match(r"^[\d.]+\Z", ip):
                _log("IP address used: %s" % ip)
                return
            if ip and len(ip) < 50 and "can't" not in ip.lower() and "error" not in ip.lower() and "page" not in ip.lower() and "working" not in ip.lower():
                _log("IP address used: %s" % ip)
                return
            if ip and ("page isn't working" in ip.lower() or "didn't send any data" in ip.lower() or "err_empty" in ip.lower()):
                _log("IP address used: (proxy failed - ERR_EMPTY_RESPONSE; try next proxy or check proxy)")
                return
        except Exception as e:
            err = str(e).split("\n")[0][:60]  # short message
            continue
    _log("IP address used: (could not detect)")


# --- Search: Google ---
def _is_google_captcha_page(driver):
    """True if Google is showing CAPTCHA / 'unusual traffic' / sorry page."""
    try:
        url = (driver.current_url or "").lower()
        if "google.com/sorry" in url or "consent.google" in url:
            return True
        body = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
        captcha_phrases = (
            "unusual traffic",
            "not a robot",
            "captcha",
            "about this page",
            "really you sending",
            "detected unusual traffic",
            "automated queries",
            "can't process your request",
            "protect our users",
        )
        if any(p in body for p in captcha_phrases):
            return True
        return False
    except Exception:
        return False


def _get_recaptcha_sitekey_from_page(driver):
    """Try to extract reCAPTCHA site key from current page (data-sitekey or k= in scripts)."""
    try:
        html = driver.page_source or ""
        # data-sitekey="6L..."
        m = re.search(r'data-sitekey\s*=\s*["\']([a-zA-Z0-9_-]{20,})["\']', html, re.I)
        if m:
            return m.group(1)
        m = re.search(r'["\'](6L[a-zA-Z0-9_-]{38,})["\']', html)
        if m:
            return m.group(1)
        m = re.search(r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']', html, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _solve_captcha_2captcha(driver):
    """Use 2Captcha API to get reCAPTCHA token and inject it. Returns True if solved."""
    try:
        import requests as _req
    except ImportError:
        return False
    key = CAPTCHA_2CAPTCHA_KEY
    if not key:
        return False
    url = driver.current_url or ""
    if "google.com" not in url:
        return False
    sitekey = _get_recaptcha_sitekey_from_page(driver)
    if not sitekey:
        _log("  2Captcha: could not find reCAPTCHA site key on page.")
        return False
    _log("  2Captcha: sending CAPTCHA to solver (sitekey=%s...)." % sitekey[:12])
    # Create task (2Captcha API v2)
    create = _req.post(
        "https://api.2captcha.com/createTask",
        json={
            "clientKey": key,
            "task": {
                "type": "RecaptchaV2TaskProxyless",
                "websiteURL": url,
                "websiteKey": sitekey,
            },
        },
        timeout=30,
    ).json()
    if create.get("errorId") != 0:
        _log("  2Captcha createTask error: %s" % create.get("errorDescription", create))
        return False
    task_id = create.get("taskId")
    if not task_id:
        return False
    # Poll for result (max ~2 min)
    for _ in range(24):
        time.sleep(5)
        result = _req.post(
            "https://api.2captcha.com/getTaskResult",
            json={"clientKey": key, "taskId": task_id},
            timeout=30,
        ).json()
        if result.get("errorId") != 0:
            _log("  2Captcha getTaskResult error: %s" % result.get("errorDescription", result))
            return False
        if result.get("status") == "ready":
            token = (result.get("solution") or {}).get("gRecaptchaResponse") or result.get("solution", {}).get("token")
            if not token:

                return False
            _log("  2Captcha: got token, injecting...")
            # Inject token and submit (Google sorry page) — pass token as script arg to avoid escaping
            try:
                driver.execute_script("""
                    var token = arguments[0];
                    var textarea = document.getElementById('g-recaptcha-response') || document.querySelector('[name="g-recaptcha-response"]');
                    if (textarea) { textarea.innerHTML = token; textarea.value = token; }
                    var f = document.querySelector('form');
                    if (f) f.submit();
                """, token)
            except Exception as e:
                _log("  2Captcha inject error: %s" % (str(e)[:50]))
            time.sleep(2)
            return True
        if result.get("status") == "processing":
            continue
        break
    _log("  2Captcha: timeout waiting for solution.")
    return False


def _solve_captcha_audio(driver):
    """Try to solve reCAPTCHA via audio challenge + speech recognition (same way as RecaptchaSolver). Returns True if solved."""
    if not AUDIO_CAPTCHA_AVAILABLE or RecaptchaSolverSelenium is None:
        return False
    try:
        solver = RecaptchaSolverSelenium(driver, log_fn=_log)
        if solver.solve_captcha():
            _log("  Audio CAPTCHA solver: solved.")
            return True
        if getattr(solver, "last_error", None):
            _log("  Audio CAPTCHA solver: %s" % solver.last_error)
    except Exception as e:
        _log("  Audio CAPTCHA solver: %s" % (str(e)[:80]))
    return False


# Max number of reCAPTCHAs to solve in a row (Google sometimes shows a second one after the first)
MAX_CAPTCHA_SOLVE_ATTEMPTS = 5
# After solving one, wait and re-check for another captcha (Google often loads a second one with a delay)
CAPTCHA_RECHECK_WAIT_SEC = 2
CAPTCHA_RECHECK_COUNT = 5   # total wait up to ~CAPTCHA_RECHECK_COUNT * CAPTCHA_RECHECK_WAIT_SEC for next captcha
# When auto solvers fail: wait and retry solvers periodically (handles second captcha that loads after first solve)
CAPTCHA_AUTO_WAIT_POLL_SEC = 3
CAPTCHA_AUTO_WAIT_TIMEOUT_SEC = 120
CAPTCHA_RETRY_SOLVER_EVERY_SEC = 12   # while waiting, retry audio/2Captcha every N seconds


def _wait_for_possible_second_captcha(driver):
    """After solving one captcha, wait and re-check so we don't exit before a second one loads. Returns True if another captcha appeared."""
    time.sleep(3)  # let page reload
    for _ in range(CAPTCHA_RECHECK_COUNT):
        if _is_google_captcha_page(driver):
            _log("  Second CAPTCHA detected, solving again...")
            return True
        time.sleep(CAPTCHA_RECHECK_WAIT_SEC)
    return False


def _wait_for_google_captcha_solve(driver):
    """If Google shows CAPTCHA, try audio solver, then 2Captcha; then wait automatically until captcha is gone (no user input)."""
    for attempt in range(1, MAX_CAPTCHA_SOLVE_ATTEMPTS + 1):
        if not _is_google_captcha_page(driver):
            return None
        if attempt > 1:
            _log("Another CAPTCHA detected (attempt %d/%d). Solving again..." % (attempt, MAX_CAPTCHA_SOLVE_ATTEMPTS))
        # 1) Try in-browser audio solver first
        if AUDIO_CAPTCHA_AVAILABLE:
            _log("Google CAPTCHA detected. Trying audio solver (reCAPTCHA audio challenge)...")
            if _solve_captcha_audio(driver):
                _log("  Waiting for page to reload...")
                if not _wait_for_possible_second_captcha(driver):
                    return None
                continue
            _log("  Audio solver failed or not available. Trying next option.")
        if CAPTCHA_2CAPTCHA_KEY:
            _log("Google CAPTCHA detected. Trying 2Captcha...")
            if _solve_captcha_2captcha(driver):
                _log("  2Captcha solved. Waiting for page to reload...")
                if not _wait_for_possible_second_captcha(driver):
                    return None
                continue
            _log("  2Captcha failed or unavailable.")
        # Wait and periodically retry solvers (so second captcha that loads later gets solved automatically)
        _log("Waiting for CAPTCHA (retrying solver every %ds, timeout %ds)..." % (CAPTCHA_RETRY_SOLVER_EVERY_SEC, CAPTCHA_AUTO_WAIT_TIMEOUT_SEC))
        deadline = time.time() + CAPTCHA_AUTO_WAIT_TIMEOUT_SEC
        last_solver_try = 0
        solved_during_wait = False
        while _is_google_captcha_page(driver) and time.time() < deadline:
            now = time.time()
            if now - last_solver_try >= CAPTCHA_RETRY_SOLVER_EVERY_SEC:
                last_solver_try = now
                if AUDIO_CAPTCHA_AVAILABLE:
                    _log("  Retrying audio solver...")
                    if _solve_captcha_audio(driver):
                        _log("  Solved. Waiting for page to reload...")
                        solved_during_wait = True
                        break
                if not solved_during_wait and CAPTCHA_2CAPTCHA_KEY:
                    _log("  Retrying 2Captcha...")
                    if _solve_captcha_2captcha(driver):
                        _log("  Solved. Waiting for page to reload...")
                        solved_during_wait = True
                        break
            time.sleep(CAPTCHA_AUTO_WAIT_POLL_SEC)
        if solved_during_wait:
            if not _wait_for_possible_second_captcha(driver):
                return None
            continue
        if not _is_google_captcha_page(driver):
            if not _wait_for_possible_second_captcha(driver):
                return None
            continue
        _log("CAPTCHA wait timeout. Continuing anyway.")
        return None
    return None


def _human_delay(min_sec=0.8, max_sec=1.8):
    """Random delay to mimic human reaction time."""
    time.sleep(random.uniform(min_sec, max_sec))


def _human_type(element, text):
    """Type text character by character with random delays (slower, more human-like)."""
    try:
        element.clear()
    except Exception:
        pass
    for c in text:
        element.send_keys(c)
        time.sleep(random.uniform(0.06, 0.22))


def _human_mouse_to(driver, element):
    """Move mouse to element with slight random offset (more human-like than instant focus)."""
    try:
        ac = ActionChains(driver)
        ac.move_to_element_with_offset(element, random.randint(-5, 5), random.randint(-2, 2))
        ac.perform()
        time.sleep(random.uniform(0.2, 0.6))
    except Exception:
        pass


# Delays for search/navigate (shorter if FASTER_NAVIGATION)
def _delay_after_google_load():
    if FASTER_NAVIGATION:
        _human_delay(0.8, 1.5)
    else:
        _human_delay(2.0, 4.0)

def _delay_before_typing():
    if FASTER_NAVIGATION:
        _human_delay(0.2, 0.5)
    else:
        _human_delay(0.5, 1.2)

def _delay_before_enter():
    if FASTER_NAVIGATION:
        _human_delay(0.4, 1.0)
    else:
        _human_delay(1.2, 2.8)

def _delay_wait_results():
    if FASTER_NAVIGATION:
        time.sleep(random.uniform(1.0, 1.8))
    else:
        time.sleep(random.uniform(2.0, 3.5))


def search_google(driver, query):
    """Load Google, run search; if CAPTCHA appears, pause for user to solve."""
    _log("Loading Google...")
    driver.get("https://www.google.com/")
    _delay_after_google_load()
    _wait_for_google_captcha_solve(driver)
    _log("Typing search query...")
    search_box = WebDriverWait(driver, 12).until(
        EC.element_to_be_clickable((By.NAME, "q"))
    )
    _human_mouse_to(driver, search_box)
    _delay_before_typing()
    _human_type(search_box, query)
    _delay_before_enter()
    search_box.send_keys(Keys.RETURN)
    _log("Waiting for results...")
    _delay_wait_results()
    _wait_for_google_captcha_solve(driver)


def go_to_results_page_google(driver, page_num):
    """Go to Google results page 1, 2, or 3 (page_num 1-based)."""
    if page_num <= 1:
        return
    url = driver.current_url
    if "google.com/sorry" in url:
        return  # CAPTCHA page; don't change URL
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params["start"] = [(page_num - 1) * 10]
    new_query = urlencode(params, doseq=True)
    new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    driver.get(new_url)
    time.sleep(0.5 if FASTER_NAVIGATION else 1)


# --- Find the Nextpital result and click it (nextpital.com) ---
FIND_LINK_TIMEOUT = 2 if FASTER_NAVIGATION else 3  # seconds per selector


def find_and_click_nextpital(driver):
    """Look for a result linking to nextpital.com or containing nextpital (works on DuckDuckGo & Google)."""
    wait = WebDriverWait(driver, FIND_LINK_TIMEOUT)
    # Selectors that work on DuckDuckGo and similar engines (most specific first)
    candidates = [
        (By.CSS_SELECTOR, "a[href*='nextpital.com']"),
        (By.XPATH, "//a[contains(@href, 'nextpital.com')]"),
        (By.CSS_SELECTOR, "a[href*='nextpital']"),
        (By.XPATH, "//a[contains(@href, 'nextpital')]"),
        (By.XPATH, "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'nextpital')]"),
        (By.XPATH, "//h3[contains(., 'nextpital') or contains(., 'Nextpital')]/ancestor::a"),
    ]
    for by, selector in candidates:
        try:
            el = wait.until(EC.element_to_be_clickable((by, selector)))
            href = (el.get_attribute("href") or "")
            text = (el.text or "").lower()
            # Accept if href or visible text mentions nextpital
            if "nextpital" in href or "nextpital" in text:
                el.click()
                return True
        except Exception:
            continue
    return False


def run_one_search(driver, query):
    """Do one full run: search keyword on Google, find nextpital on pages 1–3, click if found. Returns True if found."""
    search_google(driver, query)
    go_to_page = go_to_results_page_google
    for page in range(1, 4):
        _log(f"  Looking for nextpital.com on page {page}...")
        if page > 1:
            go_to_page(driver, page)
        if find_and_click_nextpital(driver):
            _log("  Clicked nextpital.com!")
            return True
    return False


def main():
    _log("Search engine: google")
    proxies = load_proxies()
    if proxies:
        random.shuffle(proxies)  # different IP per run: avoid always using same proxy first
        _log("Loaded %d proxy(ies) from %s" % (len(proxies), PROXY_FILE))
        # Optional: quick proxy check (Decodo: ip.decodo.com; others: icanhazip.com)
        try:
            import requests as _req
            px = {"http": proxies[0], "https": proxies[0]}
            if "decodo.com" in (proxies[0] or ""):
                r = _req.get("https://ip.decodo.com/json", proxies=px, timeout=10)
            else:
                r = _req.get("https://icanhazip.com", proxies=px, timeout=10)
            if r.ok:
                _log("Proxy check: %s" % (r.text.strip()[:60]))
        except Exception:
            pass
    elif FETCH_FREE_PROXIES:
        _log("Fetching %d proxy IPs from free list..." % FREE_PROXY_COUNT)
        proxies = fetch_free_proxies(FREE_PROXY_COUNT)
        if proxies:
            _log("Using %d fetched proxy(ies). Quality may vary." % len(proxies))
        else:
            _log("No proxies obtained. Runs will use your current IP.")
    else:
        _log("No proxies: all runs will use your current IP.")

    try:
        for run in range(1, NUM_LOOPS + 1):
            _log("")
            _log("=== Run %d / %d ===" % (run, NUM_LOOPS))
            proxy = proxies[(run - 1) % len(proxies)] if proxies else None
            driver = None
            local_proxy = None
            retried_without_proxy = False
            while True:
                try:
                    driver, local_proxy = create_chrome_driver(proxy=proxy)
                    driver.maximize_window()
                    log_ip_used(driver)
                    _log("Searching: %s" % KEYWORD)
                    found = run_one_search(driver, KEYWORD)
                    if found:
                        time.sleep(3 if FASTER_NAVIGATION else 5)
                    else:
                        _log("  nextpital.com not found on pages 1–3.")
                    break
                except KeyboardInterrupt:
                    _log("Interrupted.")
                    raise
                except Exception as e:
                    err = str(e).lower()
                    is_proxy_error = (
                        proxy
                        and not retried_without_proxy
                        and (
                            "err_tunnel_connection_failed" in err
                            or "err_proxy_connection_failed" in err
                            or "err_connection_refused" in err
                            or "proxy" in err
                        )
                    )
                    if is_proxy_error:
                        _log("  Proxy failed, retrying this run without proxy...")
                        if local_proxy:
                            _stop_pproxy(local_proxy)
                            local_proxy = None
                        if driver:
                            try:
                                driver.quit()
                            except Exception:
                                pass
                            driver = None
                        proxy = None
                        retried_without_proxy = True
                        continue
                    err_short = (str(e).split("\n")[0] or str(e))[:100]
                    _log("  Error: %s" % err_short)
                    break
                finally:
                    if driver:
                        driver.quit()
                        _log("Browser closed for this run.")
                    if local_proxy:
                        _stop_pproxy(local_proxy)
            if run < NUM_LOOPS:
                wait_between = 2 if FASTER_NAVIGATION else 3
                _log("Waiting %ds before next run..." % wait_between)
                time.sleep(wait_between)

        _log("")
        _log("Done. Completed %d runs." % NUM_LOOPS)
    except KeyboardInterrupt:
        _log("")
        _log("Stopped by user (Ctrl+C).")
        sys.exit(0)


if __name__ == "__main__":
    main()
