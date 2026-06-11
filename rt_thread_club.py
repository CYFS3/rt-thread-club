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

        # Step 2: Wait for natural OAuth redirect to club domain
        # The OAuth redirect is trusted and should bypass WAF
        logging.info("Waiting for OAuth redirect...")
        for i in range(20):
            time.sleep(1)
            url = page.url
            if url.startswith("https://club.rt-thread.org/"):
                logging.info(
                    "Redirected to club after {0}s: {1}".format(i + 1, url)
                )
                break
            if "验证码" in url or "captcha" in url.lower():
                logging.warning("CAPTCHA detected in URL after {0}s".format(i + 1))

        current_url = page.url
        logging.info("Current URL: {0}".format(current_url))

        # Step 3: Navigate to sign-in page via the natural flow
        if not current_url.startswith("https://club.rt-thread.org/"):
            # If not on club domain, try going via the main page first
            logging.info("Not on club domain, trying main page...")
            page.get("https://club.rt-thread.org/")
            time.sleep(5)
            logging.info("Main page URL: {0}".format(page.url))

        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error(
                "Cannot reach club domain. URL: {0}".format(page.url)
            )
            try:
                page.get_screenshot(path="/home/runner/paihang.png")
            except Exception:
                pass
            sys.exit(1)

        # Now click the "每日签到" navigation link
        logging.info("Looking for 每日签到 nav link...")
        sign_nav = None
        nav_selectors = [
            "xpath://a[contains(@href,'signin')]",
            "xpath://a[contains(text(),'签到')]",
            "@@text():每日签到",
            "tag:a@@href:*signin*",
        ]
        for sel in nav_selectors:
            try:
                el = page.ele(sel, timeout=3)
                if el:
                    sign_nav = el
                    logging.info("Found nav: text='{0}' href='{1}'".format(
                        el.text.strip(), el.attr("href")
                    ))
                    break
            except Exception:
                continue

        if sign_nav:
            sign_nav.click()
            time.sleep(5)
            logging.info("After click, URL: {0}".format(page.url))
        else:
            # Fallback: navigate directly
            logging.info("Nav link not found, navigating directly...")
            page.get("https://club.rt-thread.org/index/signin/index.html")
            time.sleep(5)

        # Step 4: Detect WAF and handle
        try:
            body = page.ele("tag:body", timeout=3)
            body_text = body.text if body else ""
        except Exception:
            body_text = ""

        logging.info("Page body length: {0}".format(len(body_text)))

        if "SafeLine" in body_text or "Security Detection" in body_text:
            # WAF challenge — wait for it to resolve
            logging.info("WAF challenge on sign-in page, waiting...")
            for i in range(30):
                time.sleep(1)
                try:
                    body = page.ele("tag:body", timeout=1)
                    body_text = body.text if body else ""
                except Exception:
                    body_text = ""
                if "连续签到" in body_text or "每日签到" in body_text:
                    logging.info("Real content loaded after {0}s!".format(i + 1))
                    break
                if not page.url.startswith("https://club.rt-thread.org/"):
                    logging.warning(
                        "Redirected away: {0}".format(page.url)
                    )
                    break

        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error("Lost club domain after sign-in navigation")
            sys.exit(1)

        # Step 5: Find and click the check-in button
        day_num = None
        sign_btn = None
        btn_selectors = [
            "tag:a@@class:btn-signin",
            "xpath://a[contains(@class,'btn-signin')]",
            "xpath://a[contains(text(),'签到') and not(contains(@href,'index'))]",
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
            logging.error("Page content: {0}".format(snippet))
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
                logging.error("Error with sign-in button: {0}".format(e))

        # Step 6: Read consecutive check-in days
        try:
            body = page.ele("tag:body", timeout=3)
            body_text = body.text if body else ""
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

        # Step 7: Screenshot
        try:
            time.sleep(2)
            page.get_screenshot(path="/home/runner/paihang.png")
        except Exception as e:
            logging.warning("Screenshot failed: {0}".format(e))

        return day_num
    finally:
        page.quit()
