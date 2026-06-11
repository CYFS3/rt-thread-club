# -*- coding:utf8 -*-
import re
import sys
import time
import logging
import requests
from DrissionPage import ChromiumPage, ChromiumOptions


def login_in_club_via_requests(user_name, pass_word):
    """
    Pure HTTP requests approach — avoids browser fingerprinting entirely.
    Many WAFs only challenge browser requests; plain HTTP may bypass them.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })

    # Step 1: GET the OAuth login page to get cookies
    login_url = (
        "https://www.rt-thread.org/account/user/index.html"
        "?response_type=code&authorized=yes&scope=basic"
        "&state=1588816557615&client_id=30792375"
        "&redirect_uri=https://club.rt-thread.org/index/user/login.html"
    )
    logging.info("GET login page...")
    resp = session.get(login_url, timeout=30)
    logging.info("Login page status: {0}".format(resp.status_code))

    # Extract CSRF token if present
    import re as _re
    csrf_match = _re.search(
        r'<input[^>]*name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']',
        resp.text
    )
    csrf_token = csrf_match.group(1) if csrf_match else None

    # Step 2: POST login credentials
    login_data = {
        "username": user_name,
        "password": pass_word,
    }
    if csrf_token:
        login_data["__token__"] = csrf_token

    # The login form action URL — the form likely posts to the same URL
    # or to an API endpoint. Let's try the form action.
    action_match = _re.search(
        r'<form[^>]*action=["\']([^"\']+)["\']',
        resp.text
    )
    post_url = action_match.group(1) if action_match else login_url
    if post_url.startswith("/"):
        post_url = "https://www.rt-thread.org" + post_url

    logging.info("POST login to: {0}".format(post_url))
    resp = session.post(
        post_url,
        data=login_data,
        allow_redirects=True,
        timeout=30,
    )
    logging.info("Login response status: {0}".format(resp.status_code))
    logging.info("Login response URL: {0}".format(resp.url))

    # Check if we landed on club.rt-thread.org
    if "club.rt-thread.org" in resp.url:
        logging.info("Login successful — on club domain!")
    else:
        logging.warning(
            "Not on club domain after login: {0}".format(resp.url)
        )

    # Step 3: Access the sign-in page
    signin_url = "https://club.rt-thread.org/index/signin/index.html"
    logging.info("GET sign-in page...")
    resp = session.get(signin_url, timeout=30)
    logging.info("Sign-in status: {0}, URL: {1}".format(
        resp.status_code, resp.url
    ))
    logging.info("Sign-in body length: {0}".format(len(resp.text)))

    # Check for WAF
    if "SafeLine" in resp.text or "Security Detection" in resp.text:
        logging.error("WAF blocked the sign-in page!")
        return None

    # Check if we're logged in
    if "请登录" in resp.text or "login" in resp.url.lower():
        logging.error("Not logged in on club domain!")
        return None

    # Step 4: Find the check-in button and API endpoint
    day_num = None

    if "已签到" in resp.text or "disabled" in resp.text:
        logging.info("Already checked in today!")
    elif "立即签到" in resp.text:
        # Look for the sign-in API endpoint in JavaScript
        signin_api = _re.search(
            r"signin[/\']\s*[,\)]|url:\s*['\"]([^'\"]*sign[^'\"]*)['\"]|"
            r"location\.href\s*=\s*['\"]([^'\"]*sign[^'\"]*)['\"]",
            resp.text
        )
        if signin_api:
            api_url = signin_api.group(1) or signin_api.group(2)
            logging.info("Found sign-in API: {0}".format(api_url))
            # Call the API
            if api_url.startswith("/"):
                api_url = "https://club.rt-thread.org" + api_url
            resp = session.post(api_url, timeout=30)
            logging.info("Sign-in API response: {0}".format(resp.status_code))
        else:
            logging.warning("Could not find sign-in API endpoint")
    else:
        logging.warning(
            "Unknown sign-in page state, body snippet: {0}".format(
                resp.text[:500]
            )
        )

    # Step 5: Read consecutive days
    match = _re.search(r"连续签到\s*(\d+)\s*天", resp.text)
    if match:
        day_num = match.group(1) + " 天"
        logging.info("Consecutive check-in: {0}".format(day_num))

    return day_num


def login_in_club(user_name, pass_word):
    """Try requests-based approach first, fall back to browser."""
    day_num = login_in_club_via_requests(user_name, pass_word)
    if day_num is not None:
        return day_num

    # Fallback: browser-based approach
    logging.info("Requests approach failed, trying browser...")
    return login_in_club_via_browser(user_name, pass_word)


def login_in_club_via_browser(user_name, pass_word):
    """Browser-based approach using DrissionPage CDP."""
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

        # Wait for WAF challenge to resolve
        for i in range(15):
            try:
                body = page.ele("tag:body", timeout=2)
                body_text = body.text if body else ""
            except Exception:
                body_text = ""
            if "SafeLine" not in body_text or len(body_text) > 200:
                break
            time.sleep(1)
        logging.info("Club page loaded, length: {0}".format(len(body_text)))

        # Step 1: Login via OAuth
        login_url = (
            "https://www.rt-thread.org/account/user/index.html"
            "?response_type=code&authorized=yes&scope=basic"
            "&state=1588816557615&client_id=30792375"
            "&redirect_uri=https://club.rt-thread.org/index/user/login.html"
        )
        page.get(login_url)
        page.ele('#username').input(user_name)
        time.sleep(1)
        page.ele('#password').input(pass_word)
        time.sleep(1)
        page.ele('#login').click()

        # Step 2: Wait for redirect
        logging.info("Waiting for OAuth redirect...")
        for i in range(25):
            time.sleep(1)
            if page.url.startswith("https://club.rt-thread.org/"):
                logging.info(
                    "Redirected after {0}s: {1}".format(i + 1, page.url)
                )
                break
        logging.info("Current URL: {0}".format(page.url))

        # Step 3: Ensure we're on club domain
        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.warning("Not on club domain, navigating manually...")
            page.get("https://club.rt-thread.org/")
            time.sleep(5)

        if not page.url.startswith("https://club.rt-thread.org/"):
            logging.error(
                "Cannot reach club domain: {0}".format(page.url)
            )
            sys.exit(1)

        # Step 4: Navigate to sign-in page
        nav_clicked = False
        for sel in [
            "xpath://a[contains(@href,'signin') and contains(text(),'签到')]",
            "xpath://a[contains(@href,'signin')]",
            "@@text():每日签到",
        ]:
            try:
                el = page.ele(sel, timeout=2)
                if el and "signin" in (el.attr("href") or ""):
                    el.click()
                    nav_clicked = True
                    break
            except Exception:
                continue

        if not nav_clicked:
            page.get("https://club.rt-thread.org/index/signin/index.html")

        # Step 5: Wait for real content
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
                logging.info(
                    "Sign-in content loaded after {0}s!".format(i + 1)
                )
                break
            if not page.url.startswith("https://club.rt-thread.org/"):
                logging.warning("Redirected: {0}".format(page.url))
                break

        logging.info(
            "URL: {0}, body len: {1}".format(page.url, len(body_text))
        )

        if "连续签到" not in body_text:
            snippet = body_text[:500].replace("\n", " | ")
            logging.error("Unexpected content: {0}".format(snippet))
            sys.exit(1)

        # Step 6: Click check-in button
        for sel in [
            "tag:a@@class:btn-signin",
            "xpath://a[contains(@class,'btn-signin')]",
            "xpath://a[contains(text(),'签到') and contains(@class,'btn')]",
        ]:
            try:
                btn = page.ele(sel, timeout=3)
                if btn:
                    btn_text = btn.text.strip()
                    btn_class = btn.attr("class") or ""
                    logging.info(
                        "Button: '{0}' class='{1}'".format(btn_text, btn_class)
                    )
                    if "disabled" in btn_class or "已签到" in btn_text:
                        logging.info("Already checked in!")
                    else:
                        btn.click()
                        logging.info("Sign in clicked!")
                        time.sleep(2)
                    break
            except Exception:
                continue

        # Step 7: Read days
        for line in body_text.split("\n"):
            if "连续签到" in line:
                m = re.search(r"(\d+)\s*天", line)
                if m:
                    day_num = m.group(1) + " 天"
                    logging.info(
                        "Consecutive: {0}".format(day_num)
                    )
                    break

        # Screenshot
        try:
            time.sleep(2)
            page.get_screenshot(path="/home/runner/paihang.png")
        except Exception as e:
            logging.warning("Screenshot: {0}".format(e))

        return day_num
    finally:
        page.quit()
