# -*- coding:utf8 -*-
import re
import sys
import time
import random
import logging
from DrissionPage import ChromiumPage, ChromiumOptions


def login_in_club(user_name, pass_word):
    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-dev-shm-usage')
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
        # Step 1: OAuth login
        page.get(
            "https://www.rt-thread.org/account/user/index.html"
            "?response_type=code&authorized=yes&scope=basic"
            "&state=1588816557615&client_id=30792375"
            "&redirect_uri=https://club.rt-thread.org/index/user/login.html"
        )

        page.ele('#username').input(user_name)
        time.sleep(random.uniform(0.5, 1.5))
        page.ele('#password').input(pass_word)
        time.sleep(random.uniform(0.3, 0.8))
        page.ele('#login').click()
        time.sleep(10)

        # Step 2: Navigate to sign-in page (this will work if login set cookies)
        page.get("https://club.rt-thread.org/index/signin/index.html")
        time.sleep(3)

        # Verify we're on the club domain (not redirected back to login)
        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error(
                "Login failed! Redirected to: {0}".format(page.url)
            )
            sys.exit(1)
        logging.info("Login successful, sign-in page loaded!")

        # Step 3: Find the sign-in button and determine state
        day_num = None
        sign_btn = page.ele("tag:a@@class:btn-signin", timeout=3)

        if sign_btn is None:
            logging.error("Sign-in button not found!")
        else:
            btn_text = sign_btn.text.strip()
            is_disabled = "disabled" in (sign_btn.attr("class") or "")

            if is_disabled or "已签到" in btn_text:
                logging.info("Already checked in today!")
            else:
                sign_btn.click()
                logging.info("Sign in successful!")
                time.sleep(2)

        # Step 4: Read consecutive check-in days
        try:
            body_text = page.ele("tag:body", timeout=3).text
            for line in body_text.split("\n"):
                if "连续签到" in line:
                    m = re.search(r"(\d+)\s*天", line)
                    if m:
                        day_num = m.group(1) + " 天"
                        logging.info(
                            "Consecutive check-in: {0}".format(day_num)
                        )
                        break
        except Exception as e:
            logging.error("Error reading day count: {0}".format(e))

        # Step 5: Screenshot
        try:
            time.sleep(2)
            page.get_screenshot(path="/home/runner/paihang.png")
        except Exception as e:
            logging.warning("Screenshot failed: {0}".format(e))

        return day_num
    finally:
        page.quit()
