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

        # Step 2: Navigate to sign-in page with WAF retry logic
        day_num = None
        max_attempts = 3

        for attempt in range(max_attempts):
            logging.info(
                "Loading sign-in page (attempt {0}/{1})...".format(
                    attempt + 1, max_attempts
                )
            )
            page.get(
                "https://club.rt-thread.org/index/signin/index.html"
            )

            # Wait for WAF verification to complete (up to 20 seconds)
            for i in range(20):
                time.sleep(1)
                try:
                    body = page.ele("tag:body", timeout=1)
                    body_text = body.text if body else ""
                except Exception:
                    body_text = ""

                if "连续签到" in body_text or "每日签到" in body_text:
                    logging.info(
                        "Real page loaded after {0}s!".format(i + 1)
                    )
                    break
                if "SafeLine" in body_text or "Security Detection" in body_text:
                    if i < 3:
                        logging.info("WAF challenge detected, waiting...")
                    continue

            # Check what we got
            try:
                body = page.ele("tag:body", timeout=2)
                body_text = body.text if body else ""
            except Exception:
                body_text = ""

            logging.info("Page body length: {0}".format(len(body_text)))

            if "连续签到" in body_text or "每日签到" in body_text:
                logging.info("Sign-in page loaded successfully!")
                break
            elif "SafeLine" in body_text or "Security Detection" in body_text:
                logging.warning(
                    "WAF still blocking after {0}s on attempt {1}".format(
                        20, attempt + 1
                    )
                )
                if attempt < max_attempts - 1:
                    logging.info("Retrying...")
                    time.sleep(5)
                continue
            else:
                # Unknown page content — log and try anyway
                snippet = body_text[:300].replace("\n", " | ")
                logging.warning(
                    "Unknown page content: {0}".format(snippet)
                )
                break

        # Verify we're on the club domain and have real content
        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error("Not on club domain: {0}".format(page.url))
            sys.exit(1)

        if "连续签到" not in body_text and "每日签到" not in body_text:
            logging.error(
                "Cannot access sign-in page — WAF is blocking all attempts"
            )
            try:
                page.get_screenshot(path="/home/runner/paihang.png")
            except Exception:
                pass
            sys.exit(1)

        # Step 3: Find and click the sign-in button
        sign_btn = None
        selectors = [
            "tag:a@@class:btn-signin",
            "xpath://a[contains(@class,'btn-signin')]",
            "xpath://a[contains(text(),'签到')]",
        ]
        for sel in selectors:
            try:
                el = page.ele(sel, timeout=3)
                if el:
                    sign_btn = el
                    break
            except Exception:
                continue

        if sign_btn is None:
            logging.error("Sign-in button not found with any selector!")
        else:
            try:
                btn_text = sign_btn.text.strip()
                btn_class = sign_btn.attr("class") or ""
                is_disabled = "disabled" in btn_class

                logging.info(
                    "Sign-in button: text='{0}', class='{1}'".format(
                        btn_text, btn_class
                    )
                )

                if is_disabled or "已签到" in btn_text:
                    logging.info("Already checked in today!")
                else:
                    sign_btn.click()
                    logging.info("Sign in successful!")
                    time.sleep(2)
            except Exception as e:
                logging.error(
                    "Error with sign-in button: {0}".format(e)
                )

        # Step 4: Read consecutive check-in days
        try:
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
