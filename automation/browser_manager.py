import os
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# We'll store browser profiles in a hidden directory to keep them organized
PROFILES_DIR = os.path.join(os.path.dirname(__file__), "..", ".profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

class BrowserManager:
    def __init__(self, profile_name="default"):
        self.profile_name = profile_name
        self.profile_path = os.path.join(PROFILES_DIR, profile_name)
        self.playwright = None
        self.browser_context = None
        
    def start(self, headless=False):
        """Starts Playwright and launches a persistent context."""
        logger.info(f"Starting browser for profile: {self.profile_name}")
        self.playwright = sync_playwright().start()
        
        # We use a persistent context so cookies and localStorage are saved.
        self.browser_context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_path,
            headless=headless,
            # We can add proxy settings here later
            # proxy={"server": "http://myproxy.com:3128", "username": "usr", "password": "pwd"}
            args=[
                "--disable-blink-features=AutomationControlled"
            ]
        )
        return self.browser_context
        
    def new_page(self):
        """Returns a new page from the current context."""
        if not self.browser_context:
            raise RuntimeError("Browser context not started. Call start() first.")
        return self.browser_context.new_page()
        
    def close(self):
        """Closes the browser context and stops Playwright."""
        if self.browser_context:
            logger.info(f"Closing browser for profile: {self.profile_name}")
            self.browser_context.close()
        if self.playwright:
            self.playwright.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bm = BrowserManager("test_profile")
    context = bm.start(headless=False)
    page = bm.new_page()
    page.goto("https://bot.sannysoft.com/")
    print("Browser started. Check if the automation flags are hidden.")
    import time; time.sleep(5)
    bm.close()

