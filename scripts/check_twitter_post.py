import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.twitter_poster import TwitterPoster

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_twitter():
    print("\n" + "="*50)
    print("AUTONOMOUS SOCIAL POSTER - TWITTER TEST")
    print("="*50)
    
    # Check if we have the test image
    image_path = os.path.abspath("media/outputs/nsfw_test_output.png")
    if not os.path.exists(image_path):
        print(f"Error: Could not find image at {image_path}")
        print("Please run generate_test_post.py first to create an image!")
        return
        
    print(f"\nFound test image: {image_path}")
    print("Attempting to post to Twitter...")
    
    poster = TwitterPoster(profile_name="twitter_main")
    
    success = poster.post(
        text_content="Just setting up my Twitter automation with my new AI! 🤖✨",
        image_path=image_path
    )
    
    if success:
        print("\nSUCCESS! Check your Twitter profile to see your automated post!")
    else:
        print("\nFAILED. Check the console logs above to see what went wrong.")

if __name__ == "__main__":
    test_twitter()

