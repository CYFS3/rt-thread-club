# -*- coding:utf8 -*-
"""Local auto check-in script for RT-Thread Club.
Runs directly on Windows — no WAF issues since it uses your real IP.
Double-click to run, or set up in Windows Task Scheduler for daily auto.
"""
import re
import sys
import time
import random
import logging
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

# ============================================================
# CONFIGURATION — fill in your credentials here
# ============================================================
USERNAME = "15659086907"
PASSWORD = "Wu695324"
# ============================================================

LOGIN_URL = (
    "https://www.rt-thread.org/account/user/index.html"
    "?response_type=code&authorized=yes&scope=basic"
    "&state=1588816557615&client_id=30792375"
    "&redirect_uri=https://club.rt-thread.org/index/user/login.html"
)
SIGNIN_URL = "https://club.rt-thread.org/index/signin/index.html"


def setup_logging():
    log_file = "checkin_log.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    setup_logging()
    logging.info("=== RT-Thread Club Auto Check-in ===")
    logging.info("Time: {0}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    co = ChromiumOptions()
    co.headless(False)
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--disable-blink-features=AutomationControlled')

    page = ChromiumPage(co)

    try:
        # Step 1: Login via OAuth
        logging.info("Step 1: Logging in...")
        page.get(LOGIN_URL)

        page.ele('#username').input(USERNAME)
        time.sleep(random.uniform(0.5, 1.5))
        page.ele('#password').input(PASSWORD)
        time.sleep(random.uniform(0.3, 0.8))
        page.ele('#login').click()

        # Wait for redirect
        for i in range(15):
            time.sleep(1)
            if page.url.startswith("https://club.rt-thread.org/"):
                logging.info("Logged in! Redirected to: {0}".format(page.url))
                break
        else:
            logging.warning(
                "No auto-redirect, current URL: {0}".format(page.url)
            )
            # Try manual navigation
            page.get("https://club.rt-thread.org/")
            time.sleep(3)

        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error("Login failed! URL: {0}".format(page.url))
            input("Press Enter to close browser...")
            sys.exit(1)

        # Step 2: Navigate to sign-in page
        logging.info("Step 2: Navigating to sign-in page...")
        page.get(SIGNIN_URL)
        time.sleep(3)

        # Step 3: Check sign-in status
        day_num = None
        body_text = ""
        try:
            body = page.ele("tag:body", timeout=5)
            body_text = body.text if body else ""
        except Exception:
            pass

        # Find sign-in button
        for sel in [
            "tag:a@@class:btn-signin",
            "xpath://a[contains(@class,'btn-signin')]",
        ]:
            try:
                btn = page.ele(sel, timeout=3)
                if btn:
                    btn_text = btn.text.strip()
                    btn_class = btn.attr("class") or ""
                    logging.info("Button: '{0}' (disabled={1})".format(
                        btn_text, "disabled" in btn_class
                    ))

                    if "disabled" in btn_class or "已签到" in btn_text:
                        logging.info("Already checked in today!")
                    else:
                        btn.click()
                        logging.info("Check-in successful!")
                        time.sleep(2)
                    break
            except Exception:
                continue

        # Read consecutive days
        for line in body_text.split("\n"):
            if "连续签到" in line:
                m = re.search(r"(\d+)\s*天", line)
                if m:
                    day_num = m.group(1)
                    logging.info("Consecutive check-in: {0} days".format(day_num))
                    break

        if day_num:
            logging.info("Result: Signed in, {0} consecutive days!".format(day_num))
        else:
            logging.info("Result: Check-in complete.")

    except Exception as e:
        logging.error("Unexpected error: {0}".format(e))
    finally:
        logging.info("Closing browser...")
        page.quit()
        logging.info("=== Done ===")
        # Keep window open if double-clicked
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
