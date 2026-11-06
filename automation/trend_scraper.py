import logging
import random
import time
import requests
from playwright.sync_api import sync_playwright
from .browser_manager import BrowserManager

logger = logging.getLogger(__name__)

class TrendScraper:
    def __init__(self):
        self.reddit_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def get_best_subreddit(self, subreddits):
        """
        Scrapes Reddit to find which subreddit has the highest active user count right now.
        """
        logger.info(f"Analyzing active traffic across {len(subreddits)} subreddits...")
        best_sub = subreddits[0]
        max_users = -1
        
        for sub in subreddits:
            try:
                url = f"https://www.reddit.com/r/{sub}/about.json"
                resp = requests.get(url, headers=self.reddit_headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    active_users = data.get('data', {}).get('active_user_count', 0)
                    logger.info(f"r/{sub} - {active_users} users online")
                    if active_users > max_users:
                        max_users = active_users
                        best_sub = sub
                else:
                    logger.warning(f"Failed to fetch data for r/{sub} (Status: {resp.status_code})")
            except Exception as e:
                logger.error(f"Error scraping r/{sub}: {str(e)}")
                
            time.sleep(1) # Be nice to Reddit's API

        if max_users < 0:
            best_sub = random.choice(subreddits)
            logger.warning(
                "Reddit about.json blocked or empty for all subs; "
                f"falling back to random choice r/{best_sub}"
            )
            return best_sub
            
        logger.info(f"WINNER: r/{best_sub} with {max_users} active users!")
        return best_sub

    def get_twitter_trends(self, profile_name="twitter_main"):
        """
        Uses the logged-in Twitter profile to scrape current trending topics.
        """
        logger.info("Scraping Twitter for live trending hashtags...")
        trends = []
        browser_manager = BrowserManager(profile_name)
        try:
            context = browser_manager.start(headless=True)
            page = browser_manager.new_page()
            
            # Go to the Explore page where trends live
            page.goto("https://twitter.com/explore/tabs/trending", wait_until="domcontentloaded")
            time.sleep(5) # Wait for trends to load
            
            # Twitter trends are usually in spans inside data-testid="trend"
            trend_elements = page.locator("[data-testid='trend']").all()
            for element in trend_elements[:5]: # Get top 5
                text = element.inner_text().split('\n')
                # Usually the second or third line is the actual hashtag/topic
                for line in text:
                    if line.startswith('#') or len(line.split()) <= 3:
                        # Grab the most relevant keyword
                        if "posts" not in line.lower() and "trending" not in line.lower():
                            trends.append(line)
                            break
            
            # Clean up duplicates
            trends = list(set(trends))
            logger.info(f"Found Trends: {trends}")
            
            browser_manager.close()
            return trends
            
        except Exception as e:
            logger.error(f"Failed to scrape Twitter trends: {str(e)}")
            browser_manager.close()
            # Return generic backup trends if scraper fails
            return ["#Selfie", "#OOTD", "Weekend Vibes"]

