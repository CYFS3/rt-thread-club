# -*- coding:utf8 -*-
"""Scheduled auto check-in — runs headless, logs to file. For Windows Task Scheduler."""
import re
import sys
import time
import random
import logging
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

USERNAME = "15659086907"
PASSWORD = "Wu695324"

LOGIN_URL = (
    "https://www.rt-thread.org/account/user/index.html"
    "?response_type=code&authorized=yes&scope=basic"
    "&state=1588816557615&client_id=30792375"
    "&redirect_uri=https://club.rt-thread.org/index/user/login.html"
)
SIGNIN_URL = "https://club.rt-thread.org/index/signin/index.html"
LOG_FILE = r"C:\Users\RTT\Desktop\rt-thread-club\checkin_log.txt"


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logging.info("=== Auto Check-in Start ===")

    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--window-size=1920,1080')
    co.set_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )

    page = ChromiumPage(co)

    try:
        # Login
        logging.info("Logging in...")
        page.get(LOGIN_URL)
        page.ele('#username').input(USERNAME)
        time.sleep(random.uniform(0.5, 1.5))
        page.ele('#password').input(PASSWORD)
        time.sleep(random.uniform(0.3, 0.8))
        page.ele('#login').click()

        for i in range(20):
            time.sleep(1)
            if page.url.startswith("https://club.rt-thread.org/"):
                logging.info("Redirected: {0}".format(page.url))
                break
        else:
            logging.info("No redirect, navigating manually...")
            page.get("https://club.rt-thread.org/")
            time.sleep(3)

        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error("Login failed!")
            return 1

        # Navigate to sign-in
        page.get(SIGNIN_URL)
        time.sleep(3)

        # Parse page
        body_text = ""
        try:
            body = page.ele("tag:body", timeout=5)
            body_text = body.text if body else ""
        except Exception:
            pass

        if "连续签到" not in body_text:
            logging.error("Sign-in page not loaded properly!")
            return 1

        # Find and click button
        day_num = None
        for sel in [
            "tag:a@@class:btn-signin",
            "xpath://a[contains(@class,'btn-signin')]",
        ]:
            try:
                btn = page.ele(sel, timeout=3)
                if btn:
                    btn_text = btn.text.strip()
                    btn_class = btn.attr("class") or ""
                    if "disabled" in btn_class or "已签到" in btn_text:
                        logging.info("Already checked in!")
                    else:
                        btn.click()
                        logging.info("Check-in clicked!")
                        time.sleep(2)
                    break
            except Exception:
                continue

        # Read days
        for line in body_text.split("\n"):
            if "连续签到" in line:
                m = re.search(r"(\d+)\s*天", line)
                if m:
                    day_num = m.group(1)
                    logging.info("{0} consecutive days!".format(day_num))
                    break

        if day_num:
            logging.info("SUCCESS: {0} days".format(day_num))
        else:
            logging.info("SUCCESS: check-in done")

        return 0

    except Exception as e:
        logging.error("Error: {0}".format(e))
        return 1
    finally:
        page.quit()
        logging.info("=== Done ===")


if __name__ == "__main__":
    sys.exit(main())
