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
        # Step 0: Visit club domain first to clear WAF challenge
        logging.info("Pre-warming: visiting club domain...")
        page.get("https://club.rt-thread.org/")
        time.sleep(5)
        logging.info("Club main page: {0}".format(page.url))

        # If WAF challenge, wait for it to resolve
        for i in range(15):
            try:
                body = page.ele("tag:body", timeout=2)
                body_text = body.text if body else ""
            except Exception:
                body_text = ""
            if "SafeLine" not in body_text or len(body_text) > 200:
                break
            time.sleep(1)

        logging.info("Club page length: {0}".format(len(body_text)))

        # Step 1: Login via OAuth
        login_url = (
            "https://www.rt-thread.org/account/user/index.html"
            "?response_type=code&authorized=yes&scope=basic"
            "&state=1588816557615&client_id=30792375"
            "&redirect_uri=https://club.rt-thread.org/index/user/login.html"
        )
        page.get(login_url)

        page.ele('#username').input(user_name)
        time.sleep(random.uniform(0.5, 1.5))
        page.ele('#password').input(pass_word)
        time.sleep(random.uniform(0.3, 0.8))
        page.ele('#login').click()

        # Step 2: Wait for redirect to club domain
        logging.info("Waiting for OAuth redirect...")
        for i in range(25):
            time.sleep(1)
            url = page.url
            if url.startswith("https://club.rt-thread.org/"):
                logging.info(
                    "Redirected to club after {0}s: {1}".format(i + 1, url)
                )
                break

        current_url = page.url
        if not current_url.startswith("https://club.rt-thread.org/"):
            # OAuth redirect didn't happen — try manual navigation
            logging.warning(
                "No auto-redirect, navigating manually..."
            )
            # Go to club main page first
            page.get("https://club.rt-thread.org/")
            time.sleep(5)

            if page.url.startswith("https://club.rt-thread.org/"):
                logging.info("Manually reached club domain")
            else:
                logging.error(
                    "Cannot reach club domain: {0}".format(page.url)
                )
                try:
                    page.get_screenshot(path="/home/runner/paihang.png")
                except Exception:
                    pass
                sys.exit(1)

        # Step 3: Navigate to sign-in page
        logging.info("Navigating to sign-in page...")

        # Try clicking nav link first
        nav_found = False
        nav_selectors = [
            "xpath://a[contains(@href,'signin') and contains(text(),'签到')]",
            "xpath://a[contains(@href,'signin')]",
            "@@text():每日签到",
        ]
        for sel in nav_selectors:
            try:
                el = page.ele(sel, timeout=3)
                if el:
                    text = el.text.strip()
                    href = el.attr("href") or ""
                    logging.info(
                        "Nav link: text='{0}' href='{1}'".format(text, href)
                    )
                    if "signin" in href:
                        el.click()
                        nav_found = True
                        break
            except Exception:
                continue

        if not nav_found:
            logging.info("No nav link, using direct URL...")
            page.get(
                "https://club.rt-thread.org/index/signin/index.html"
            )

        time.sleep(5)
        logging.info("After nav, URL: {0}".format(page.url))

        # Step 4: Wait for real page content
        day_num = None
        body_text = ""
        for i in range(30):
            time.sleep(1)
            try:
                body = page.ele("tag:body", timeout=1)
                body_text = body.text if body else ""
            except Exception:
                body_text = ""

            if "连续签到" in body_text or "每日签到" in body_text:
                logging.info("Sign-in content loaded after {0}s!".format(i + 1))
                break

            if not page.url.startswith("https://club.rt-thread.org/"):
                logging.warning(
                    "Redirected away: {0}".format(page.url)
                )
                break

        logging.info("Final URL: {0}".format(page.url))
        logging.info("Body length: {0}".format(len(body_text)))

        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error("Not on club domain")
            sys.exit(1)

        if "连续签到" not in body_text and "每日签到" not in body_text:
            snippet = body_text[:500].replace("\n", " | ")
            logging.error("Wrong page content: {0}".format(snippet))
            try:
                page.get_screenshot(path="/home/runner/paihang.png")
            except Exception:
                pass
            sys.exit(1)

        # Step 5: Find and click the check-in button
        sign_btn = None
        btn_selectors = [
            "tag:a@@class:btn-signin",
            "xpath://a[contains(@class,'btn-signin')]",
            "xpath://a[contains(text(),'签到') and contains(@class,'btn')]",
        ]
        for sel in btn_selectors:
            try:
                el = page.ele(sel, timeout=3)
                if el:
                    sign_btn = el
                    break
            except Exception:
                continue

        if sign_btn is None:
            logging.error("Sign-in button not found!")
            snippet = body_text[:500].replace("\n", " | ")
            logging.error("Page: {0}".format(snippet))
        else:
            try:
                btn_text = sign_btn.text.strip()
                btn_class = sign_btn.attr("class") or ""
                is_disabled = "disabled" in btn_class

                logging.info(
                    "Button: text='{0}' class='{1}'".format(
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
                    "Button error: {0}".format(e)
                )

        # Step 6: Read consecutive check-in days
        for line in body_text.split("\n"):
            if "连续签到" in line:
                m = re.search(r"(\d+)\s*天", line)
                if m:
                    day_num = m.group(1) + " 天"
                    logging.info(
                        "Consecutive check-in: {0}".format(day_num)
                    )
                    break

        # Step 7: Screenshot
        try:
            time.sleep(2)
            page.get_screenshot(path="/home/runner/paihang.png")
        except Exception as e:
            logging.warning("Screenshot failed: {0}".format(e))

        return day_num
    finally:
        page.quit()
