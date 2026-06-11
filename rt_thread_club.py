# -*- coding:utf8 -*-
import re
import sys
import time
import logging
import requests
from DrissionPage import ChromiumPage, ChromiumOptions

LOGIN_URL = (
    "https://www.rt-thread.org/account/user/index.html"
    "?response_type=code&authorized=yes&scope=basic"
    "&state=1588816557615&client_id=30792375"
    "&redirect_uri=https://club.rt-thread.org/index/user/login.html"
)
SIGNIN_URL = "https://club.rt-thread.org/index/signin/index.html"
CLUB_HOME = "https://club.rt-thread.org/"


def login_in_club(user_name, pass_word):
    """Try requests first, then browser with club-native login flow."""
    day_num = _try_requests(user_name, pass_word)
    if day_num is not None:
        return day_num
    logging.info("Requests approach failed, trying browser...")
    return _try_browser(user_name, pass_word)


def _try_requests(user_name, pass_word):
    """Pure HTTP approach — may bypass WAF that targets browsers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })

    # GET login page
    r = session.get(LOGIN_URL, timeout=30)
    logging.info("[req] Login page: {0}".format(r.status_code))

    # Extract CSRF token
    m = re.search(
        r'<input[^>]*name=["\']__token__["\'][^>]*value=["\']([^"\']+)["\']',
        r.text
    )
    token = m.group(1) if m else None

    # Extract form action
    m = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', r.text)
    action = m.group(1) if m else LOGIN_URL
    if action.startswith("/"):
        action = "https://www.rt-thread.org" + action

    # POST login
    data = {"username": user_name, "password": pass_word}
    if token:
        data["__token__"] = token

    r = session.post(action, data=data, allow_redirects=True, timeout=30)
    logging.info("[req] After POST: status={0} url={1}".format(
        r.status_code, r.url
    ))

    if "club.rt-thread.org" not in r.url:
        logging.warning("[req] Not redirected to club domain")
        return None

    # GET sign-in page
    r = session.get(SIGNIN_URL, timeout=30)
    logging.info("[req] Sign-in: status={0} len={1}".format(
        r.status_code, len(r.text)
    ))

    if "SafeLine" in r.text or "Security Detection" in r.text:
        logging.error("[req] WAF blocked sign-in page")
        return None

    if "请登录" in r.text:
        logging.error("[req] Not logged in on club domain")
        return None

    day_num = _parse_days(r.text)
    logging.info("[req] Result: {0}".format(day_num))
    return day_num


def _try_browser(user_name, pass_word):
    """Browser-based login directly via club domain navigation."""
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
        # Step 1: Go to club homepage first
        logging.info("Loading club homepage...")
        page.get(CLUB_HOME)
        time.sleep(5)
        logging.info("Club homepage URL: {0}".format(page.url))

        # Step 2: Click "登录" on club homepage
        logging.info("Looking for login link on club page...")
        login_clicked = False
        for sel in [
            "xpath://a[text()='登录' and not(contains(text(),'请登录'))]",
            "@@text():登录",
            "xpath://a[contains(text(),'登')]",
        ]:
            try:
                el = page.ele(sel, timeout=3)
                if el:
                    text = el.text.strip()
                    href = el.attr("href") or ""
                    logging.info("Found: text='{0}' href='{1}'".format(text, href))
                    if text == "登录" or "login" in href.lower():
                        el.click()
                        login_clicked = True
                        break
            except Exception:
                continue

        if not login_clicked:
            logging.info("Login link not found, using OAuth URL directly...")
            page.get(LOGIN_URL)
            time.sleep(3)

        # Step 3: Check where we are and login if needed
        time.sleep(3)
        current_url = page.url
        logging.info("After login click, URL: {0}".format(current_url))

        # If we're on the OAuth login page, fill in credentials
        if "rt-thread.org/account" in current_url:
            logging.info("On OAuth page, filling credentials...")
            try:
                page.ele('#username').input(user_name)
                time.sleep(1)
                page.ele('#password').input(pass_word)
                time.sleep(1)
                page.ele('#login').click()
                time.sleep(10)
            except Exception as e:
                logging.error("Login form error: {0}".format(e))

        # Step 4: Wait for redirect to club domain
        for i in range(20):
            time.sleep(1)
            if page.url.startswith("https://club.rt-thread.org/"):
                logging.info("On club domain after {0}s!".format(i + 1))
                break

        # Step 5: If still not on club domain, navigate there
        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.info("Not redirected, navigating to club home...")
            page.get(CLUB_HOME)
            time.sleep(5)

        logging.info("Current URL: {0}".format(page.url))

        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error("Cannot reach club domain. Aborting.")
            try:
                page.get_screenshot(path="/home/runner/paihang.png")
            except Exception:
                pass
            sys.exit(1)

        # Step 6: Navigate to sign-in page
        page.get(SIGNIN_URL)
        time.sleep(5)

        # Wait for real content (handle WAF)
        day_num = None
        body_text = ""
        for i in range(30):
            time.sleep(1)
            try:
                body = page.ele("tag:body", timeout=1)
                body_text = body.text if body else ""
            except Exception:
                body_text = ""
            if "连续签到" in body_text:
                logging.info("Content loaded after {0}s!".format(i + 1))
                break
            if not page.url.startswith("https://club.rt-thread.org/"):
                logging.warning("Redirected: {0}".format(page.url))
                break

        logging.info("URL: {0}, len: {1}".format(page.url, len(body_text)))

        if "连续签到" not in body_text:
            snippet = body_text[:500].replace("\n", " | ")
            logging.error("Bad content: {0}".format(snippet))
            try:
                page.get_screenshot(path="/home/runner/paihang.png")
            except Exception:
                pass
            sys.exit(1)

        # Step 7: Click sign-in button
        for sel in [
            "tag:a@@class:btn-signin",
            "xpath://a[contains(@class,'btn-signin')]",
        ]:
            try:
                btn = page.ele(sel, timeout=3)
                if btn:
                    btn_text = btn.text.strip()
                    btn_class = btn.attr("class") or ""
                    logging.info("Btn: '{0}' class='{1}'".format(btn_text, btn_class))
                    if "disabled" in btn_class or "已签到" in btn_text:
                        logging.info("Already checked in!")
                    else:
                        btn.click()
                        logging.info("Check-in clicked!")
                        time.sleep(2)
                    break
            except Exception:
                continue

        # Step 8: Parse days
        day_num = _parse_days(body_text)

        # Screenshot
        try:
            time.sleep(2)
            page.get_screenshot(path="/home/runner/paihang.png")
        except Exception as e:
            logging.warning("Screenshot: {0}".format(e))

        return day_num
    finally:
        page.quit()


def _parse_days(text):
    m = re.search(r"连续签到\s*(\d+)\s*天", text)
    if m:
        result = m.group(1) + " 天"
        logging.info("Consecutive days: {0}".format(result))
        return result
    return None
