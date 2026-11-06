import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.content_config import load_content_config
from brain.llm_client import LLMClient
from db.db_setup import record_generation, recent_combo_keys, recent_topics
from media.sd_client import StableDiffusionClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def list_styles(config):
    print(f"\nStyles in {config.path}:")
    for style in config.styles:
        flag = "on " if style.enabled else "off"
        print(f"  [{flag}] {style.id:20}  {style.display_name()}")
        print(f"         {style.topic}")
    print(f"\nGraphic levels: {config.graphic_level}")
    print(f"Photos always explicit: {config.images_always_explicit}")
    print(f"Subject: {config.subject or '(none)'}")


def test_generation(plan, config):
    """
    Tests Ollama + Automatic1111 without posting to social media.
    """
    logger.info("=== Starting generation test ===")
    logger.info("Style: %s", plan.style.id)
    logger.info("Topic: %s", plan.topic)
    logger.info("Graphic level this post: %s", plan.graphic_level)
    logger.info("Seed: %s combo: %s", plan.seed, plan.combo_key)

    llm = LLMClient()
    sd = StableDiffusionClient(output_dir="media/outputs")

    content = llm.generate_post_content(
        plan.topic,
        graphic_level=plan.graphic_level,
        style_lock=config.photography,
        always_explicit=config.images_always_explicit,
        avoid_scenes=recent_topics(),
        unique_key=plan.combo_key,
    )

    if not content:
        logger.error("Failed to get content from Ollama. Ensure Ollama is running and the model is downloaded.")
        return

    caption = content.get("caption", "Default caption")
    llm_sd = (content.get("sd_prompt") or "").strip()
    sd_prompt = llm_sd or plan.sd_prompt
    if llm_sd:
        logger.info("Using LLM sd_prompt")
    else:
        logger.info("LLM sd_prompt missing; falling back to planned prompt")

    logger.info("\n[Generated Caption]: %s", caption)
    logger.info("[Generated SD Prompt]: %s\n", sd_prompt)

    logger.info("Sending prompt to Automatic1111...")
    image_path = sd.generate_image(
        prompt=sd_prompt,
        negative_prompt=config.negative_prompt,
        filename="nsfw_test_output.png",
        steps=config.image.steps,
        width=config.image.width,
        height=config.image.height,
        cfg_scale=config.image.cfg_scale,
        sampler_name=config.image.sampler,
        seed=plan.seed,
        clip_skip=config.image.clip_skip,
    )

    if image_path and os.path.exists(image_path):
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
        logger.info("=== Success! Image saved to %s ===", image_path)
        logger.info("Please review the generated image and text.")
    else:
        logger.error("Failed to generate image. Ensure Automatic1111 is running with the --api flag.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a caption + image from content.toml (does not post)."
    )
    parser.add_argument("--list", action="store_true", help="List pic styles and exit")
    parser.add_argument("--style", help="Style id from content.toml (e.g. neon-egirl)")
    parser.add_argument("--topic", help="One-off custom topic; ignores --style")
    args = parser.parse_args()

    config = load_content_config()

    if args.list:
        list_styles(config)
        return

    print("\n" + "=" * 50)
    print("AUTONOMOUS SOCIAL POSTER - TEST MODE")
    print("=" * 50)

    avoid = recent_combo_keys()
    if args.topic:
        plan = config.plan_generation(topic_override=args.topic.strip(), avoid_combo_keys=avoid)
        print("\nUsing custom topic with a fresh pose/outfit/seed.")
    elif args.style:
        plan = config.plan_generation(style_id=args.style, avoid_combo_keys=avoid)
        print(f"\nUsing style {plan.style.id}: {plan.style.display_name()}")
    else:
        list_styles(config)
        try:
            choice = input(
                "\nStyle id, or a custom topic (Enter = random enabled style):\n> "
            ).strip()
        except EOFError:
            choice = ""
        if not choice:
            plan = config.plan_generation(avoid_combo_keys=avoid)
            print(f"Random style {plan.style.id}: {plan.style.display_name()}")
        else:
            try:
                plan = config.plan_generation(style_id=choice, avoid_combo_keys=avoid)
                print(f"Using style {plan.style.id}: {plan.style.display_name()}")
            except KeyError:
                plan = config.plan_generation(topic_override=choice, avoid_combo_keys=avoid)
                print("Using custom topic.")

    print(f"This shot: {plan.graphic_level} | {plan.pose or 'n/a pose'} | {plan.outfit or 'n/a outfit'}")
    print("\nStarting generation process...")
    test_generation(plan, config)


if __name__ == "__main__":
    main()
