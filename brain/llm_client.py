import requests
import json
import logging

logger = logging.getLogger(__name__)

# Default Ollama API URL
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
# You should download an uncensored model in Ollama, e.g. `ollama run dolphin-mixtral` or similar
DEFAULT_MODEL = "dolphin-llama3" 

GRAPHIC_INSTRUCTIONS = {
    "sfw": (
        "You are an AI persona manager for an 18+ lifestyle creator. "
        "Write a catchy social caption. Caption tone: casual, not sexual."
    ),
    "suggestive": (
        "You are an AI persona manager for a flirty 18+ adult creator. "
        "Write a catchy social caption. Caption tone: flirty and teasing, not pornographic."
    ),
    "explicit": (
        "You are an AI persona manager for an explicit 18+ adult creator. "
        "Write a catchy, engaging social media caption with hashtags. "
        "Caption tone: direct, sexual, first-person."
    ),
    "nsfw": (
        "You are an AI persona manager for an uncensored 18+ NSFW creator. "
        "Write a catchy social caption. Caption tone: horny, blunt, NSFW hashtags welcome."
    ),
}


class LLMClient:
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model

    def generate_post_content(
        self,
        topic,
        twitter_trends=None,
        graphic_level="explicit",
        style_lock=None,
        always_explicit=True,
        avoid_scenes=None,
        unique_key=None,
    ):
        """
        Calls local Ollama to generate a caption and a Stable Diffusion prompt.
        """
        level = (graphic_level or "explicit").lower()
        if level not in GRAPHIC_INSTRUCTIONS:
            level = "explicit"
        lock = style_lock or (
            "amateur photography, taken on iPhone 14, candid snapshot, flash photography, "
            "unedited, raw, gritty, visible skin pores, natural skin texture, "
            "slight imperfections, messy background"
        )
        image_rules = (
            "For the sd_prompt, ALWAYS include keywords like "
            f"'{lock}'. The subject is an 18+ adult. Never depict anyone under 18. "
        )
        if always_explicit or level in {"explicit", "nsfw"}:
            image_rules += (
                "The sd_prompt MUST be explicit 18+ NSFW every time: uncensored adult anatomy, "
                "sexual posing, graphic detail. Do not fade into tasteful or implied nudity. "
                "Invent a NEW pose, outfit, angle, and location so this photo does not look like a prior post. "
            )
        else:
            image_rules += "Match the caption tone in the sd_prompt. "
        if unique_key:
            image_rules += f"Uniqueness token (do not repeat prior compositions): {unique_key}. "
        system_prompt = GRAPHIC_INSTRUCTIONS[level] + " " + image_rules

        trends_context = ""
        if twitter_trends and len(twitter_trends) > 0:
            trends_context = f"CURRENT VIRAL TWITTER TRENDS TO PIGGYBACK ON: {', '.join(twitter_trends)}\nUse at least one of these trends in your caption naturally."

        avoid_context = ""
        if avoid_scenes:
            listed = "\n".join(f"- {scene}" for scene in avoid_scenes[:8])
            avoid_context = f"\nDO NOT repeat these recent scenes:\n{listed}\n"

        user_prompt = f"""Write a post about: {topic}.
{trends_context}
{avoid_context}
CRITICAL RULES FOR CAPTION:
- Must be written in the FIRST PERSON ("I", "me", "my", "mine").
- DO NOT use third person ("this girl", "she", "her").
- NEVER mention the word "iPhone", "camera", "photography", or how the photo was taken.
- The caption is just what you write on Twitter, NOT a description of the photo itself.
- Sound like a real, authentic human girl posting a selfie.
- Keep it casual, maybe a little flirty or direct.
- Do NOT sound like an advertisement or a bot.
- Include 1-2 relevant hashtags.
- Keep the caption under 220 characters so it fits on X/Twitter.

CRITICAL RULES FOR sd_prompt:
- Unique composition every time (new pose + outfit + camera + setting).
- Follow the image rules above for how explicit the photo is.

Provide the output as JSON with two keys: 'caption' and 'sd_prompt'."""

        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
            "format": "json"
        }

        logger.info(
            "Sending prompt to Ollama (%s) graphic_level=%s topic: %s",
            self.model,
            level,
            topic,
        )
        try:
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            response_text = data.get("response", "{}")
            
            try:
                content = json.loads(response_text)
                return content
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from Ollama response.")
                return None

        except Exception as e:
            logger.error(f"Failed to generate text via Ollama: {str(e)}")
            return None

    def generate_caption(self, voice, photo_hint="", extra=None):
        """Caption only. Used when posting real photos from a folder."""
        hint_line = ""
        if photo_hint:
            hint_line = (
                f"The file is named roughly: {photo_hint}. "
                "Use that only as a loose vibe, not as facts about the photo.\n"
            )
        extra_line = f"{extra}\n" if extra else ""
        payload = {
            "model": self.model,
            "prompt": (
                f"{voice.strip()}\n\n"
                f"{hint_line}{extra_line}"
                "Write one social caption for this photo.\n"
                "You cannot see the image, so do not invent specific clothing or body details.\n"
                "Return JSON with one key: caption."
            ),
            "stream": False,
            "format": "json",
        }
        logger.info("Asking Ollama (%s) for a persona caption", self.model)
        try:
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            parsed = json.loads(data.get("response", "{}"))
            caption = (parsed.get("caption") or "").strip()
            return caption or None
        except Exception as e:
            logger.error("Failed to generate caption via Ollama: %s", e)
            return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = LLMClient()
    # Ensure Ollama is running before testing
    # result = client.generate_post_content("a cozy morning drinking coffee in lingerie")
    # print(result)

