import argparse
import logging
import os
import random
import subprocess
import time
from datetime import datetime

import requests

from brain.content_config import load_content_config
from brain.llm_client import LLMClient
from media.sd_client import StableDiffusionClient
from media.photo_library import filename_hint, mark_used, take_next_photo
from automation.reddit_poster import RedditPoster
from automation.twitter_poster import TwitterPoster
from automation.trend_scraper import TrendScraper
from db.db_setup import record_generation, recent_combo_keys, recent_topics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OLLAMA_TAGS = "http://127.0.0.1:11434/api/tags"
OLLAMA_GENERATE = "http://127.0.0.1:11434/api/generate"


def ensure_ollama(timeout=90):
    """Start the ollama container if needed. A1111 + Ollama together will swap on 11GB RAM."""
    subprocess.run(["docker", "start", "ollama"], check=False, capture_output=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(OLLAMA_TAGS, timeout=2)
            if resp.ok:
                logger.info("Ollama is up.")
                return True
        except Exception:
            time.sleep(1)
    logger.error("Ollama did not become ready in time.")
    return False


def release_ollama():
    """Unload the model and stop the container so A1111 has RAM."""
    try:
        requests.post(
            OLLAMA_GENERATE,
            json={"model": "dolphin-llama3", "keep_alive": 0},
            timeout=30,
        )
    except Exception:
        pass
    subprocess.run(["docker", "stop", "ollama"], check=False, capture_output=True)
    logger.info("Ollama stopped to free RAM.")


def caption_for_photo(persona, photo, config):
    hint = filename_hint(photo)
    caption = None
    if ensure_ollama():
        try:
            llm = LLMClient()
            caption = llm.generate_caption(persona.voice, photo_hint=hint)
        finally:
            release_ollama()
    if not caption:
        if persona.fallback_captions:
            caption = random.choice(persona.fallback_captions)
            logger.info("Using fallback caption for %s", persona.id)
        else:
            caption = "slow night. come talk to me."
    if len(caption) > 270:
        caption = caption[:267].rstrip() + "..."
    return caption


def post_from_library(config, persona=None):
    logger.info("=== PHOTO LIBRARY CYCLE ===")
    persona = persona or config.pick_persona()
    logger.info("Persona: %s (%s)", persona.id, persona.display_name)
    logger.info("Unused photos: %s in %s", persona.photo_count(), persona.photos_dir)

    try:
        photo = take_next_photo(persona.photos_dir, pick=config.photo_pick)
    except FileNotFoundError as e:
        logger.error("%s", e)
        return False

    logger.info("Selected photo: %s", photo)
    caption = caption_for_photo(persona, photo, config)
    logger.info("Caption: %s", caption)

    image_path = str(photo)
    reddit_ok = False
    twitter_ok = False

    logger.info("--- Starting Social Media Distribution ---")
    subreddit = random.choice(persona.subreddits or config.subreddits or ["selfies"])
    try:
        reddit = RedditPoster(profile_name=persona.reddit_profile)
        reddit_ok = bool(
            reddit.post(subreddit=subreddit, title=caption, image_path=image_path)
        )
        logger.info("Reddit r/%s: %s", subreddit, "ok" if reddit_ok else "failed")
    except Exception as e:
        logger.error("Reddit automation crashed: %s", e)

    try:
        twitter = TwitterPoster(profile_name=persona.twitter_profile)
        twitter_ok = bool(twitter.post(text_content=caption, image_path=image_path))
        logger.info("Twitter: %s", "ok" if twitter_ok else "failed")
    except Exception as e:
        logger.error("Twitter automation crashed: %s", e)

    if reddit_ok or twitter_ok:
        used = mark_used(photo, persona.used_dir)
        record_generation(
            style_id=persona.id,
            combo_key=str(used),
            graphic_level="photos",
            topic=photo.name,
            caption=caption,
            media_path=str(used),
        )
        logger.info("=== PHOTO CYCLE COMPLETE (posted) ===")
        return True

    logger.error("Both platforms failed; photo stays in the unused folder.")
    logger.info("=== PHOTO CYCLE COMPLETE (not posted) ===")
    return False


def generate_and_post(config, style=None, persona=None):
    logger.info("=== STARTING NEW AUTOMATION CYCLE ===")

    persona = persona or config.pick_persona()
    logger.info("Persona profiles: %s (reddit=%s twitter=%s)",
                persona.id, persona.reddit_profile, persona.twitter_profile)

    # 1. Scrape Trends to maximize reach
    scraper = TrendScraper()
    subreddit_pool = persona.subreddits or config.subreddits
    best_subreddit = scraper.get_best_subreddit(subreddit_pool)
    # Skip live Twitter scraping: headless Chrome corrupts the saved login profile.
    twitter_trends = ["#Selfie", "#OOTD", "late night"]

    plan = config.plan_generation(style=style, avoid_combo_keys=recent_combo_keys())
    logger.info(
        "Selected style %s (%s) graphic_level=%s seed=%s combo=%s",
        plan.style.id,
        plan.style.display_name(),
        plan.graphic_level,
        plan.seed,
        plan.combo_key,
    )
    logger.info("Selected base topic: %s", plan.topic)
    
    # 2. Generate Content (Ollama, then free RAM for A1111)
    llm = LLMClient()
    sd = StableDiffusionClient(output_dir="media/outputs")

    if not ensure_ollama():
        logger.error("Failed to start Ollama. Skipping this cycle.")
        return
    try:
        content = llm.generate_post_content(
            plan.topic,
            twitter_trends=twitter_trends,
            graphic_level=plan.graphic_level,
            style_lock=config.photography,
            always_explicit=config.images_always_explicit,
            avoid_scenes=recent_topics(),
            unique_key=plan.combo_key,
        )
    finally:
        release_ollama()
    if not content:
        logger.error("Failed to generate content from Ollama. Skipping this cycle.")
        return
        
    caption = content.get("caption", "Just chilling ✨")
    llm_sd = (content.get("sd_prompt") or "").strip()
    sd_prompt = llm_sd or plan.sd_prompt
    if llm_sd:
        logger.info("Using LLM sd_prompt")
    else:
        logger.info("LLM sd_prompt missing; falling back to planned prompt")

    logger.info(f"Caption: {caption}")
    logger.info(f"SD Prompt: {sd_prompt}")
    
    # Generate unique filename based on timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"post_{timestamp}.png"
    
    image_path = sd.generate_image(
        prompt=sd_prompt,
        negative_prompt=config.negative_prompt,
        filename=filename,
        steps=config.image.steps,
        width=config.image.width,
        height=config.image.height,
        cfg_scale=config.image.cfg_scale,
        sampler_name=config.image.sampler,
        seed=plan.seed,
        clip_skip=config.image.clip_skip,
    )
    
    if not image_path or not os.path.exists(image_path):
        logger.error("Failed to generate image from A1111. Skipping this cycle.")
        return
        
    logger.info(f"Image successfully generated: {image_path}")

    # 3. Post to Social Media
    logger.info("--- Starting Social Media Distribution ---")
    reddit_success = False
    twitter_success = False

    # Reddit
    try:
        reddit = RedditPoster(profile_name=persona.reddit_profile)
        reddit_success = bool(
            reddit.post(
                subreddit=best_subreddit,
                title=caption,
                image_path=image_path,
            )
        )
        if reddit_success:
            logger.info("✅ Reddit post successful.")
        else:
            logger.error("❌ Reddit post failed.")
    except Exception as e:
        logger.error(f"Reddit automation crashed: {str(e)}")

    # Twitter
    try:
        twitter = TwitterPoster(profile_name=persona.twitter_profile)
        twitter_success = bool(
            twitter.post(
                text_content=caption,
                image_path=image_path,
            )
        )
        if twitter_success:
            logger.info("✅ Twitter post successful.")
        else:
            logger.error("❌ Twitter post failed.")
    except Exception as e:
        logger.error(f"Twitter automation crashed: {str(e)}")

    if reddit_success or twitter_success:
        record_generation(
            style_id=plan.style.id,
            combo_key=plan.combo_key,
            graphic_level=plan.graphic_level,
            topic=plan.topic,
            caption=caption,
            sd_prompt=sd_prompt,
            seed=plan.seed,
            media_path=image_path,
        )
        logger.info("=== AUTOMATION CYCLE COMPLETE (posted) ===")
        return True

    logger.error("Both platforms failed; generation not recorded as used.")
    logger.info("=== AUTOMATION CYCLE COMPLETE (not posted) ===")
    return False

def run_cycle(config):
    if config.mode == "photos":
        return post_from_library(config)
    return bool(generate_and_post(config))


def main_loop():
    print("\n" + "="*50)
    print("AUTONOMOUS SOCIAL POSTER - MASTER LOOP")
    print("="*50)

    config = load_content_config()
    print(f"\nMode: {config.mode}")
    if config.mode == "photos":
        for persona in config.enabled_personas():
            print(
                f"  - {persona.id}: {persona.display_name} "
                f"({persona.photo_count()} unused photos in {persona.photos_dir})"
            )
        print("Drop original photos you have rights to into the photos folder.")
    else:
        enabled = config.enabled_styles()
        print(f"Loaded {len(enabled)} enabled generate styles from {config.path.name}.")
    print("Edit content.toml to change personas or schedule. Press Ctrl+C to stop.\n")
    
    while True:
        try:
            # 1. Run the poster
            run_cycle(config)
            
            # 2. Sleep between posts (configured in content.toml)
            sleep_seconds = random.randint(config.sleep_min_seconds, config.sleep_max_seconds)
            sleep_hours = round(sleep_seconds / 3600, 2)
            
            logger.info(f"Sleeping for {sleep_hours} hours to mimic human behavior...")
            time.sleep(sleep_seconds)
            
        except KeyboardInterrupt:
            logger.info("Bot manually stopped by user.")
            break
        except Exception as e:
            logger.error(f"Critical error in main loop: {str(e)}")
            # If it hard crashes, sleep for 10 minutes then try again
            time.sleep(600)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous social poster")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single generate-and-post cycle, then exit",
    )
    parser.add_argument("--list", action="store_true", help="List personas and unused photo counts")
    args = parser.parse_args()
    config = load_content_config()
    if args.list:
        print(f"mode={config.mode} pick={config.photo_pick}")
        for persona in config.personas:
            flag = "on" if persona.enabled else "off"
            print(
                f"  [{flag}] {persona.id:16} {persona.display_name}  "
                f"{persona.photo_count()} unused  {persona.photos_dir}"
            )
        raise SystemExit(0)
    if args.once:
        run_cycle(config)
    else:
        main_loop()

