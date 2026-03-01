# Run with a real GUI on the VPS (like your laptop)

If the script keeps getting **"bot detected"** on the VPS (no real display), you can install a **lightweight desktop + VNC** so Chrome runs in a real window. Then run the script **from inside that desktop** — same as on your laptop (audio reCAPTCHA solver works better with a real display).

---

## 1. On the VPS: install desktop + VNC (one-time)

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install -y tigervnc-standalone-server tigervnc-common xfce4 xfce4-goodies dbus-x11
```

- **TigerVNC** = remote desktop server  
- **Xfce** = lightweight desktop (low RAM)

---

## 2. Set VNC password (one-time)

```bash
vncpasswd
```

Enter a password (you’ll use it when connecting from your PC). Optional: set a view-only password or skip (n).

---

## 3. Start the VNC desktop

**Start a VNC session (resolution 1280x720, 24-bit color):**

```bash
vncserver -geometry 1280x720 -depth 24 :1
```

If `:1` is in use, use `:2` instead. Note the display number (e.g. `:1`).

**Optional – run the script in that session in the background:**

```bash
export DISPLAY=:1
cd ~/paython_ranking
# Don't use run_on_vps.sh here if you want a real GUI: it would use xvfb. Run Python directly with DISPLAY set:
chmod +x run_on_vps.sh
DISPLAY=:1 ./run_on_vps.sh
```

Because `DISPLAY=:1` is set, the script will **not** use xvfb and **not** force headless — Chrome will open in the VNC desktop.

**Or run from inside the VNC desktop (recommended):**

1. From your **PC**, connect with a VNC client to `YOUR_VPS_IP:5901` (for display `:1`; use 5902 for `:2`).  
   - Windows: TigerVNC Viewer, RealVNC, or TightVNC  
   - Mac: built-in Screen Sharing (vnc://YOUR_VPS_IP:5901) or TigerVNC  
2. In the VNC window you’ll see the Xfce desktop. Open a **terminal**.
3. In that terminal:
   ```bash
   cd ~/paython_ranking
   ./run_on_vps.sh
   ```
4. Chrome will open **inside the VNC desktop**; you can watch it. The script behaves like on your laptop (real display → less “bot detected”).

---

## 4. Stop VNC when you’re done

```bash
vncserver -kill :1
```

(Use `:2` if you started `:2`.)

---

## 5. Optional: start VNC on boot

Create `~/.vnc/xstartup` (if it doesn’t exist):

```bash
mkdir -p ~/.vnc
echo '#!/bin/sh
unset SESSION_MANAGER
exec startxfce4' > ~/.vnc/xstartup
chmod +x ~/.vnc/xstartup
```

Then start VNC at login or via a systemd user service if you want it always available.

---

## Summary

| Method              | Chrome runs in…     | CAPTCHA / “bot detected”      |
|---------------------|---------------------|--------------------------------|
| Headless / xvfb     | No real window      | Often “bot detected”          |
| **VNC + desktop**   | **Real window (VNC)**| **Closer to laptop behavior** |

Your 4GB VPS can run Xfce + Chrome; if it feels slow, close other apps in the VNC session.
