import logging
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.browser_manager import BrowserManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

LOGIN_TIMEOUT_SEC = 600
POLL_SEC = 2


def notify(title, body):
    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "-u", "critical", title, body],
            check=False,
        )
    logger.info("%s — %s", title, body)


def first_page(browser_manager):
    pages = browser_manager.browser_context.pages
    if pages:
        return pages[0]
    return browser_manager.new_page()


def twitter_logged_in(page):
    url = (page.url or "").lower()
    title = (page.title() or "").lower()
    if "login" in url or "/i/flow" in url:
        return False
    if "/home" in url and "log in" not in title:
        return True
    if "home / x" in title or " / x" in title:
        return True
    selectors = [
        "[data-testid='SideNav_NewTweet_Button']",
        "[data-testid='tweetTextarea_0']",
        "[data-testid='AppTabBar_Home_Link']",
        "[data-testid='AppTabBar_Profile_Link']",
        "[data-testid='primaryColumn']",
        "nav [aria-label='Home']",
        "a[href='/home']",
    ]
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    try:
        if page.get_by_role("button", name="Post").count() > 0:
            return True
    except Exception:
        pass
    return False


def reddit_logged_in(page):
    url = (page.url or "").lower()
    path = url.split("?", 1)[0]
    if "/login" in path or "/register" in path:
        return False
    try:
        body = (page.inner_text("body") or "").lower()
        if "logged in as" in body:
            return True
    except Exception:
        body = ""
    selectors = [
        "#USER_DROPDOWN_ID",
        "shreddit-header-action-menu",
        "[data-testid='user-drawer-button']",
        "button[aria-label='Open inbox']",
        "a[href='/notifications']",
        "reddit-header-action-item[action-id='user-drawer']",
        "faceplate-tracker[noun='user_drawer']",
        "a[href*='/user/']",
        "button:has-text('Create')",
    ]
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    try:
        if page.get_by_role("button", name="Create").count() > 0:
            return True
    except Exception:
        pass
    return False


def wait_until(browser_manager, is_logged_in, platform, timeout=LOGIN_TIMEOUT_SEC):
    deadline = time.time() + timeout
    last_log = 0
    while time.time() < deadline:
        try:
            for page in list(browser_manager.browser_context.pages):
                if is_logged_in(page):
                    logger.info("%s login detected on %s (%s).", platform, page.url, page.title())
                    return True
        except Exception as e:
            logger.warning("Login check error (%s): %s", platform, e)
        now = time.time()
        if now - last_log >= 15:
            remaining = int(deadline - now)
            urls = []
            try:
                urls = [p.url for p in browser_manager.browser_context.pages]
            except Exception:
                pass
            logger.info(
                "Waiting for %s login in the desktop browser... %ss left urls=%s",
                platform,
                remaining,
                urls,
            )
            last_log = now
        time.sleep(POLL_SEC)
    return False


def login_platform(profile_name, url, is_logged_in, platform, home_url=None):
    notify(
        f"Log into {platform}",
        f"A browser window opened. Sign in to {platform}, including any 2FA.",
    )
    bm = BrowserManager(profile_name)
    try:
        bm.start(headless=False)
        page = first_page(bm)
        page.bring_to_front()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        already = False
        for p in list(bm.browser_context.pages):
            if is_logged_in(p):
                already = True
                page = p
                break
        if already:
            logger.info("Already logged into %s (%s).", platform, page.url)
            time.sleep(2)
            return True
        ok = wait_until(bm, is_logged_in, platform)
        if ok and home_url:
            try:
                page.goto(home_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)
            except Exception as e:
                logger.warning("Could not navigate to home after %s login: %s", platform, e)
        return ok
    finally:
        bm.close()


def login_to_platforms():
    twitter_ok = login_platform(
        profile_name="twitter_main",
        url="https://x.com/login",
        is_logged_in=twitter_logged_in,
        platform="Twitter/X",
        home_url="https://x.com/home",
    )
    if not twitter_ok:
        logger.error("Twitter/X login was not detected in time. Session not saved.")
        return False

    reddit_ok = login_platform(
        profile_name="reddit_main",
        url="https://www.reddit.com/login/",
        is_logged_in=reddit_logged_in,
        platform="Reddit",
        home_url="https://www.reddit.com/",
    )
    if not reddit_ok:
        logger.error("Reddit login was not detected in time. Session not saved.")
        return False

    notify("Logins saved", "Twitter/X and Reddit sessions are stored in .profiles/")
    logger.info("Successfully saved session cookies for both platforms.")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if login_to_platforms() else 1)
