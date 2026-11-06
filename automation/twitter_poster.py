import logging
import time
from .browser_manager import BrowserManager

logger = logging.getLogger(__name__)


class TwitterPoster:
    def __init__(self, profile_name="twitter_main"):
        self.browser_manager = BrowserManager(profile_name)

    def _page(self):
        pages = self.browser_manager.browser_context.pages
        return pages[0] if pages else self.browser_manager.new_page()

    def post(self, text_content: str, image_path: str = None):
        """
        Navigates to Twitter/X and creates a post.
        Requires the user to have logged in manually at least once on this profile.
        """
        try:
            self.browser_manager.start(headless=False)
            page = self._page()

            logger.info("Navigating to Twitter/X...")
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)

            if page.locator("[data-testid='SideNav_NewTweet_Button']").count() == 0 and \
               page.locator("[data-testid='tweetTextarea_0']").count() == 0:
                logger.error("Not logged into Twitter! Run login_accounts.py first.")
                self.browser_manager.close()
                return False

            if len(text_content) > 270:
                logger.warning("Caption is %s chars; truncating to 270 for X.", len(text_content))
                text_content = text_content[:267].rstrip() + "..."

            logger.info("Writing caption...")
            box = page.locator("[data-testid='tweetTextarea_0']").first
            if box.count() == 0:
                page.locator("[data-testid='SideNav_NewTweet_Button']").click()
                time.sleep(1)
                box = page.locator("[data-testid='tweetTextarea_0']").first
            box.click()
            time.sleep(0.5)
            page.keyboard.type(text_content, delay=40)

            if image_path:
                logger.info("Uploading image: %s", image_path)
                file_input = page.locator("input[type='file'][data-testid='fileInput']").first
                file_input.set_input_files(image_path)
                try:
                    page.locator("[data-testid='attachments'] img").first.wait_for(timeout=30000)
                except Exception:
                    logger.warning("Attachment preview did not appear; waiting anyway.")
                time.sleep(2)

            logger.info("Waiting for Post button to enable...")
            post_btn = page.locator("[data-testid='tweetButtonInline']").last
            if post_btn.count() == 0:
                post_btn = page.locator("[data-testid='tweetButton']").last
            for _ in range(30):
                disabled = post_btn.get_attribute("aria-disabled")
                if disabled in (None, "false"):
                    break
                time.sleep(1)
            logger.info("Clicking post button...")
            try:
                post_btn.click(timeout=5000)
            except Exception:
                logger.info("Pointer click failed, sending Control+Enter.")
                page.keyboard.press("Control+Enter")

            sent = False
            try:
                page.get_by_text("Your post was sent").wait_for(timeout=15000)
                sent = True
            except Exception:
                logger.info("No toast yet, trying Control+Enter.")
                page.keyboard.press("Control+Enter")
                try:
                    page.get_by_text("Your post was sent").wait_for(timeout=10000)
                    sent = True
                except Exception:
                    logger.warning("Did not see 'Your post was sent' toast.")
            time.sleep(2)
            logger.info("After submit, URL is %s sent=%s", page.url, sent)
            page.screenshot(path="media/outputs/last_twitter_submit.png")
            self.browser_manager.close()
            return sent

        except Exception as e:
            logger.error("Failed to post to Twitter: %s", e)
            try:
                self.browser_manager.close()
            except Exception:
                pass
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    poster = TwitterPoster("twitter_test")
    # poster.post("Hello world! This is an automated test.", "path/to/image.png")
