import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.reddit_poster import RedditPoster

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_reddit():
    print("\n" + "="*50)
    print("AUTONOMOUS SOCIAL POSTER - REDDIT TEST")
    print("="*50)
    
    # Check if we have the test image
    image_path = os.path.abspath("media/outputs/nsfw_test_output.png")
    if not os.path.exists(image_path):
        print(f"Error: Could not find image at {image_path}")
        print("Please run generate_test_post.py first to create an image!")
        return
        
    print(f"\nFound test image: {image_path}")
    print("Attempting to post to Reddit (r/test)...")
    
    poster = RedditPoster(profile_name="reddit_main")
    
    # Post to r/test to avoid getting banned while we are testing!
    success = poster.post(
        subreddit="test",
        title="Just a test post from my new AI!",
        image_path=image_path
    )
    
    if success:
        print("\nSUCCESS! Check r/test to see your automated post!")
    else:
        print("\nFAILED. Check the console logs above to see what went wrong.")

if __name__ == "__main__":
    test_reddit()

