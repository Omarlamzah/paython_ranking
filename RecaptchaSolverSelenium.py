"""
Selenium version of the audio reCAPTCHA solver.
Same approach as RecaptchaSolver (DrissionPage): click checkbox, use audio challenge,
download MP3, convert to WAV, recognize with Google Speech API, submit.
Use with: from RecaptchaSolverSelenium import RecaptchaSolverSelenium
"""
import os
import random
import time
import urllib.request
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class RecaptchaSolverSelenium:
    """Solve reCAPTCHA using audio challenge + speech recognition (Selenium WebDriver)."""

    TEMP_DIR = os.getenv("TEMP") if os.name == "nt" else "/tmp"
    TIMEOUT_STANDARD = 12
    TIMEOUT_SHORT = 3
    TIMEOUT_DETECTION = 0.5

    def __init__(self, driver, log_fn=None):
        """Initialize with a Selenium WebDriver. log_fn(msg) is called for debug messages if set."""
        self.driver = driver
        self.log = log_fn or (lambda msg: None)
        self.last_error = None

    def solve_captcha(self) -> bool:
        """
        Attempt to solve the reCAPTCHA on the current page.
        Returns True if solved, False otherwise. Sets self.last_error on failure.
        """
        self.last_error = None
        try:
            self.driver.switch_to.default_content()
            time.sleep(2)  # let sorry page / reCAPTCHA iframe finish loading
            # Find main reCAPTCHA iframe (checkbox) — try title and src
            iframe_checkbox = None
            for sel in ("iframe[title*='reCAPTCHA']", "iframe[title*='recaptcha']", "iframe[src*='recaptcha']"):
                try:
                    iframe_checkbox = WebDriverWait(self.driver, self.TIMEOUT_SHORT).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    break
                except Exception:
                    continue
            if not iframe_checkbox:
                self.last_error = "reCAPTCHA checkbox iframe not found"
                self.driver.switch_to.default_content()
                return False
            self.driver.switch_to.frame(iframe_checkbox)
            time.sleep(0.3)

            checkbox = WebDriverWait(self.driver, self.TIMEOUT_STANDARD).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".rc-anchor-content"))
            )
            # JavaScript click to avoid "element click intercepted" by the "Try again later" dialog overlay
            self.driver.execute_script("arguments[0].click();", checkbox)
            self.driver.switch_to.default_content()
            time.sleep(0.8)

            if self._is_solved():
                return True

            # Challenge iframe (audio) — wait for it to appear after checkbox click
            time.sleep(0.5)
            iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe")
            challenge_frame = None
            for i, f in enumerate(iframes):
                title = (f.get_attribute("title") or "").lower()
                if "challenge" in title:
                    challenge_frame = (i, f)
                    break
            if not challenge_frame:
                for i in range(len(iframes)):
                    try:
                        self.driver.switch_to.default_content()
                        self.driver.switch_to.frame(i)
                        self.driver.find_element(By.ID, "recaptcha-audio-button")
                        challenge_frame = (i, None)
                        break
                    except Exception:
                        continue
            if not challenge_frame:
                self.last_error = "audio challenge iframe not found (Try again later?)"
                self.driver.switch_to.default_content()
                return False

            self.driver.switch_to.default_content()
            self.driver.switch_to.frame(challenge_frame[0])
            time.sleep(0.3)

            audio_btn = WebDriverWait(self.driver, self.TIMEOUT_STANDARD).until(
                EC.presence_of_element_located((By.ID, "recaptcha-audio-button"))
            )
            self.driver.execute_script("arguments[0].click();", audio_btn)
            time.sleep(0.8)

            if self._is_detected():
                self.driver.switch_to.default_content()
                self.last_error = "Try again later (bot detected)"
                raise Exception("Captcha detected bot behavior")

            audio_el = WebDriverWait(self.driver, self.TIMEOUT_STANDARD).until(
                EC.presence_of_element_located((By.ID, "audio-source"))
            )
            audio_src = audio_el.get_attribute("src")
            if not audio_src:
                self.last_error = "audio source URL empty"
                self.driver.switch_to.default_content()
                return False

            text_response = self._process_audio_challenge(audio_src)
            if not text_response:
                self.last_error = "speech recognition failed or empty"
                self.driver.switch_to.default_content()
                return False

            response_input = self.driver.find_element(By.ID, "audio-response")
            response_input.clear()
            response_input.send_keys(text_response.lower())
            verify_btn = self.driver.find_element(By.ID, "recaptcha-verify-button")
            self.driver.execute_script("arguments[0].click();", verify_btn)
            time.sleep(0.8)
            self.driver.switch_to.default_content()

            return self._is_solved()
        except Exception as e:
            if not self.last_error:
                self.last_error = str(e)[:80]
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            return False

    def _process_audio_challenge(self, audio_url: str) -> Optional[str]:
        """Download audio, convert to WAV, recognize with Google Speech API."""
        try:
            import pydub
            import speech_recognition
        except ImportError:
            return None
        mp3_path = os.path.join(self.TEMP_DIR, f"{random.randrange(1, 10000)}.mp3")
        wav_path = os.path.join(self.TEMP_DIR, f"{random.randrange(1, 10000)}.wav")
        try:
            urllib.request.urlretrieve(audio_url, mp3_path)
            sound = pydub.AudioSegment.from_mp3(mp3_path)
            sound.export(wav_path, format="wav")
            recognizer = speech_recognition.Recognizer()
            with speech_recognition.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            return recognizer.recognize_google(audio)
        except Exception:
            return None
        finally:
            for path in (mp3_path, wav_path):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    def _is_solved(self) -> bool:
        """Check if reCAPTCHA checkbox is in solved state."""
        try:
            self.driver.switch_to.default_content()
            iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[title*='reCAPTCHA']")
            for f in iframes:
                self.driver.switch_to.frame(f)
                try:
                    checkmark = self.driver.find_element(By.CSS_SELECTOR, ".recaptcha-checkbox-checkmark")
                    if checkmark.get_attribute("style"):
                        self.driver.switch_to.default_content()
                        return True
                except Exception:
                    pass
                self.driver.switch_to.default_content()
        except Exception:
            pass
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass
        return False

    def _is_detected(self) -> bool:
        """Check for 'Try again later' (bot detected)."""
        try:
            self.driver.find_element(By.XPATH, "//*[contains(text(), 'Try again later')]")
            return True
        except Exception:
            return False
