import logging
import time
from .browser_manager import BrowserManager

logger = logging.getLogger(__name__)


class RedditPoster:
    def __init__(self, profile_name="reddit_main"):
        self.browser_manager = BrowserManager(profile_name)

    def _page(self):
        pages = self.browser_manager.browser_context.pages
        return pages[0] if pages else self.browser_manager.new_page()

    def post(self, subreddit: str, title: str, image_path: str):
        """
        Navigates to a specific subreddit and creates an image post.
        Requires the user to have logged in manually at least once.
        """
        try:
            self.browser_manager.start(headless=False)
            page = self._page()

            logger.info("Navigating to r/%s submit page...", subreddit)
            page.goto(
                f"https://www.reddit.com/r/{subreddit}/submit",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            time.sleep(4)

            if "/login" in (page.url or "").split("?", 1)[0]:
                logger.error("Not logged into Reddit! Run login_accounts.py first.")
                self.browser_manager.close()
                return False

            logger.info("Entering title...")
            try:
                page.get_by_placeholder("Title").fill(title, timeout=8000)
            except Exception:
                page.locator("textarea:not([name*='recaptcha'])").first.fill(title, force=True)

            logger.info("Uploading image: %s", image_path)
            uploaded = False
            try:
                with page.expect_file_chooser(timeout=8000) as fc_info:
                    page.get_by_role("button", name="Image").first.click()
                fc_info.value.set_files(image_path)
                uploaded = True
            except Exception as e:
                logger.warning("File chooser path failed (%s); using hidden input.", e)

            if not uploaded:
                file_input = page.locator("input[type='file']").last
                file_input.set_input_files(image_path)

            time.sleep(4)

            if subreddit.lower() != "test":
                logger.info("Marking post as NSFW...")
                try:
                    page.get_by_role("button", name="Add tags").click(timeout=3000)
                    time.sleep(0.5)
                    nsfw = page.get_by_role("button", name="NSFW")
                    if nsfw.count() > 0:
                        nsfw.first.click(force=True)
                except Exception:
                    pass

            logger.info("Clicking Post button...")
            page.get_by_role("button", name="Post").first.click(force=True)

            time.sleep(8)
            logger.info("After submit, URL is %s", page.url)
            page.screenshot(path="media/outputs/last_reddit_submit.png")
            self.browser_manager.close()
            return True

        except Exception as e:
            logger.error("Failed to post to Reddit: %s", e)
            try:
                self.browser_manager.close()
            except Exception:
                pass
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    poster = RedditPoster("reddit_test")
    # poster.post("test", "My automated NSFW test post", "path/to/image.png")
