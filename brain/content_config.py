import hashlib
import logging
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

import tomllib

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "content.toml"

VALID_GRAPHIC_LEVELS = ("sfw", "suggestive", "explicit", "nsfw")

DEFAULT_VARIETY = {
    "poses": [
        "lying on her back looking at the camera",
        "on all fours looking over her shoulder",
        "sitting with legs apart",
        "kneeling, back arched",
        "mirror selfie from a high angle",
        "from behind looking over her shoulder",
        "stretched out on rumpled sheets",
    ],
    "outfits": [
        "completely nude",
        "lingerie",
        "oversized shirt only",
        "thong only",
        "open robe",
    ],
    "settings": [
        "messy bedroom at night",
        "bathroom vanity",
        "unmade bed in daylight",
        "gaming room",
    ],
    "lighting": [
        "on-camera flash",
        "warm lamp light",
        "neon LED lighting",
        "harsh overhead light",
    ],
    "camera": [
        "front camera mirror selfie",
        "handheld phone snapshot",
        "high angle",
        "arm's length selfie",
    ],
}


@dataclass(frozen=True)
class Persona:
    id: str
    display_name: str
    photos_dir: Path
    used_dir: Path
    voice: str
    enabled: bool = True
    subreddits: list[str] = field(default_factory=list)
    fallback_captions: list[str] = field(default_factory=list)
    reddit_profile: str = "reddit_main"
    twitter_profile: str = "twitter_main"

    def photo_count(self) -> int:
        from media.photo_library import list_photos
        return len(list_photos(self.photos_dir))


@dataclass(frozen=True)
class Style:
    id: str
    topic: str
    enabled: bool = True
    name: str = ""
    clothing: str = ""
    setting: str = ""
    extra_sd_tags: str = ""

    def display_name(self) -> str:
        return self.name or self.id


@dataclass(frozen=True)
class ImageSettings:
    width: int = 512
    height: int = 768
    steps: int = 20
    cfg_scale: float = 7.0
    sampler: str = "Euler a"
    clip_skip: int = 2


@dataclass(frozen=True)
class GenerationPlan:
    style: Style
    graphic_level: str
    topic: str
    sd_prompt: str
    combo_key: str
    seed: int
    pose: str = ""
    outfit: str = ""
    setting: str = ""
    lighting: str = ""
    camera: str = ""


@dataclass
class ContentConfig:
    styles: list[Style]
    subject: str
    hair: str
    eyes: str
    body: str
    details: str
    quality: str
    framing: str
    photography: str
    negative_prompt: str
    graphic_level: str
    graphic_levels: list[str]
    images_always_explicit: bool
    require_nude: bool
    image: ImageSettings
    subreddits: list[str]
    sleep_min_seconds: int
    sleep_max_seconds: int
    path: Path
    variety: dict[str, list[str]] = field(default_factory=dict)
    mode: str = "photos"
    photo_pick: str = "oldest"
    personas: list[Persona] = field(default_factory=list)

    def enabled_personas(self) -> list[Persona]:
        return [p for p in self.personas if p.enabled]

    def pick_persona(self, persona_id: str | None = None) -> Persona:
        if persona_id:
            wanted = persona_id.strip().lower()
            for persona in self.personas:
                if persona.id.lower() == wanted:
                    return persona
            known = ", ".join(p.id for p in self.personas) or "(none)"
            raise KeyError(f"Unknown persona {persona_id!r}. Known ids: {known}")
        enabled = self.enabled_personas()
        if not enabled:
            raise ValueError(f"No enabled personas in {self.path}. Add a [[personas]] block.")
        with_photos = [p for p in enabled if p.photo_count() > 0]
        if with_photos:
            return random.choice(with_photos)
        return random.choice(enabled)

    def enabled_styles(self) -> list[Style]:
        return [s for s in self.styles if s.enabled]

    def get_style(self, style_id: str) -> Style:
        wanted = style_id.strip().lower()
        for style in self.styles:
            if style.id.lower() == wanted:
                return style
        known = ", ".join(s.id for s in self.styles) or "(none)"
        raise KeyError(f"Unknown style {style_id!r}. Known ids: {known}")

    def pick_style(self, style_id: str | None = None) -> Style:
        if style_id:
            style = self.get_style(style_id)
            if not style.enabled:
                logger.warning("Style %s is disabled in content.toml; using it anyway.", style.id)
            return style
        enabled = self.enabled_styles()
        if not enabled:
            raise ValueError(
                f"No enabled styles in {self.path}. Set enabled = true on at least one [[styles]] block."
            )
        return random.choice(enabled)

    def pick_graphic_level(self) -> str:
        return random.choice(self.graphic_levels)

    def prompt_seed(self, style: Style) -> str:
        return self._compose_topic(style)

    def plan_generation(
        self,
        style: Style | None = None,
        style_id: str | None = None,
        avoid_combo_keys: list[str] | None = None,
        topic_override: str | None = None,
    ) -> GenerationPlan:
        style = style or self.pick_style(style_id)
        avoid = set(avoid_combo_keys or [])
        graphic_level = self.pick_graphic_level()
        seed = random.randint(1, 2_147_483_647)

        chosen = {}
        combo_key = ""
        for _ in range(40):
            chosen = {
                key: random.choice(values)
                for key, values in self.variety.items()
                if values
            }
            if self.require_nude:
                chosen["outfits"] = random.choice(self._nude_outfits())
            combo_key = _combo_key(style.id, chosen)
            if combo_key not in avoid:
                break
        else:
            chosen["nonce"] = str(seed)
            combo_key = _combo_key(style.id, chosen)

        if topic_override:
            topic = topic_override
        else:
            topic = self._compose_topic(style, chosen)

        if self.images_always_explicit:
            topic += ", explicit 18+ NSFW, uncensored adult body, sexual posing"

        sd_prompt = self.build_sd_prompt(style, chosen)
        return GenerationPlan(
            style=style,
            graphic_level=graphic_level,
            topic=topic,
            sd_prompt=sd_prompt,
            combo_key=combo_key,
            seed=seed,
            pose=chosen.get("poses", ""),
            outfit=chosen.get("outfits", ""),
            setting=chosen.get("settings", "") or style.setting,
            lighting=chosen.get("lighting", ""),
            camera=chosen.get("camera", ""),
        )

    def _nude_outfits(self) -> list[str]:
        markers = ("nude", "naked", "bare", "thong only", "nothing but", "no clothes")
        pool = [
            item for item in self.variety.get("outfits", [])
            if any(marker in item.lower() for marker in markers)
        ]
        return pool or ["completely nude", "nude, no clothes"]

    def build_sd_prompt(self, style: Style, chosen: dict[str, str] | None = None) -> str:
        """Short prompt with looks first. SD 1.5 only honors ~75 tokens."""
        chosen = chosen or {}
        parts = [
            self.quality or "photorealistic, beautiful attractive woman",
            self.subject,
            self.hair,
            self.eyes,
            self.body,
            self.details,
            self.framing or "full body",
        ]
        if self.require_nude:
            parts.append("nude, naked, bare breasts, nipples")
        outfit = chosen.get("outfits") or style.clothing
        if outfit and not self.require_nude:
            parts.append(outfit)
        elif outfit and self.require_nude:
            parts.append(outfit)
        pose = chosen.get("poses", "")
        setting = chosen.get("settings") or style.setting
        lighting = chosen.get("lighting", "")
        camera = chosen.get("camera", "")
        if pose:
            parts.append(pose)
        if setting:
            parts.append(setting)
        if lighting:
            parts.append(lighting)
        if camera:
            parts.append(camera)
        if self.photography:
            parts.append(self.photography)
        if style.extra_sd_tags:
            parts.append(style.extra_sd_tags)
        if self.images_always_explicit or self.require_nude:
            parts.append("explicit")
        cleaned = []
        seen = set()
        for part in parts:
            text = " ".join(str(part).split()).strip(" ,")
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
        return ", ".join(cleaned)

    def _compose_topic(self, style: Style, chosen: dict[str, str] | None = None) -> str:
        parts = []
        if self.subject:
            parts.append(self.subject)
        parts.append(style.topic)
        outfit = (chosen or {}).get("outfits") or style.clothing
        setting = (chosen or {}).get("settings") or style.setting
        pose = (chosen or {}).get("poses", "")
        lighting = (chosen or {}).get("lighting", "")
        camera = (chosen or {}).get("camera", "")
        if outfit:
            parts.append(f"wearing {outfit}" if not outfit.startswith("completely") else outfit)
        if pose:
            parts.append(pose)
        if setting:
            parts.append(f"in {setting}")
        if lighting:
            parts.append(lighting)
        if camera:
            parts.append(camera)
        if self.photography:
            parts.append(self.photography)
        if style.extra_sd_tags:
            parts.append(style.extra_sd_tags)
        return ", ".join(part.strip() for part in parts if part and part.strip())


def _combo_key(style_id: str, chosen: dict[str, str]) -> str:
    raw = "|".join(f"{k}={chosen.get(k, '')}" for k in ("poses", "outfits", "settings", "lighting", "camera"))
    digest = hashlib.sha1(f"{style_id}|{raw}".encode()).hexdigest()[:16]
    return f"{style_id}:{digest}"


def _as_str(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def _as_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_str_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[/,|]+", value)
        return [p.strip() for p in parts if p.strip()]
    return [str(x).strip() for x in value if str(x).strip()]


def parse_graphic_levels(value) -> list[str]:
    levels = [part.lower() for part in _as_str_list(value or "explicit")]
    if not levels:
        levels = ["explicit"]
    invalid = [level for level in levels if level not in VALID_GRAPHIC_LEVELS]
    if invalid:
        raise ValueError(
            f"generation.graphic_level must be one or more of {VALID_GRAPHIC_LEVELS}, got {invalid}"
        )
    # preserve order, drop dupes
    seen = []
    for level in levels:
        if level not in seen:
            seen.append(level)
    return seen


def load_content_config(path: Path | None = None) -> ContentConfig:
    config_path = Path(path) if path else DEFAULT_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"Content config not found: {config_path}")

    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)

    subject_raw = raw.get("subject") or {}
    subject = _as_str(subject_raw.get("description"))
    hair = _as_str(subject_raw.get("hair"))
    eyes = _as_str(subject_raw.get("eyes"))
    body = _as_str(subject_raw.get("body"))
    details = _as_str(subject_raw.get("details"))
    look = raw.get("look") or {}
    quality = _as_str(look.get("quality"), "photorealistic, beautiful attractive woman")
    framing = _as_str(look.get("framing"), "full body")
    photography = _as_str(look.get("photography"))
    gen = raw.get("generation") or {}
    graphic_levels = parse_graphic_levels(gen.get("graphic_level", "explicit"))
    graphic_level = "/".join(graphic_levels)
    images_always_explicit = _as_bool(gen.get("images_always_explicit"), True)
    require_nude = _as_bool(gen.get("require_nude"), False)
    negative_prompt = _as_str(
        gen.get("negative_prompt"),
        "ugly, deformed, bad anatomy, text, watermark, child, loli, teen",
    )

    img = raw.get("image") or {}
    image = ImageSettings(
        width=int(img.get("width", 512)),
        height=int(img.get("height", 768)),
        steps=int(img.get("steps", 20)),
        cfg_scale=float(img.get("cfg_scale", 7.0)),
        sampler=_as_str(img.get("sampler"), "Euler a") or "Euler a",
        clip_skip=int(img.get("clip_skip", 2)),
    )

    reddit = raw.get("reddit") or {}
    subreddits = [str(s).strip() for s in reddit.get("subreddits") or [] if str(s).strip()]
    if not subreddits:
        subreddits = ["selfies"]

    schedule = raw.get("schedule") or {}
    sleep_min = int(schedule.get("sleep_min_seconds", 7200))
    sleep_max = int(schedule.get("sleep_max_seconds", 12600))
    if sleep_min < 1 or sleep_max < sleep_min:
        raise ValueError("schedule.sleep_min_seconds must be >= 1 and <= sleep_max_seconds")

    variety_raw = raw.get("variety") or {}
    variety = {}
    for key in ("poses", "outfits", "settings", "lighting", "camera"):
        items = _as_str_list(variety_raw.get(key)) or list(DEFAULT_VARIETY[key])
        variety[key] = items

    styles = []
    for i, item in enumerate(raw.get("styles") or []):
        style_id = _as_str(item.get("id"))
        topic = _as_str(item.get("topic"))
        if not style_id or not topic:
            raise ValueError(f"styles[{i}] needs both id and topic in {config_path}")
        styles.append(
            Style(
                id=style_id,
                topic=topic,
                enabled=_as_bool(item.get("enabled"), True),
                name=_as_str(item.get("name"), style_id),
                clothing=_as_str(item.get("clothing")),
                setting=_as_str(item.get("setting")),
                extra_sd_tags=_as_str(item.get("extra_sd_tags")),
            )
        )
    if not styles:
        raise ValueError(f"No [[styles]] defined in {config_path}")

    poster = raw.get("poster") or {}
    mode = _as_str(poster.get("mode"), "photos").lower() or "photos"
    if mode not in {"photos", "generate"}:
        raise ValueError(f"poster.mode must be 'photos' or 'generate', got {mode!r}")
    photo_pick = _as_str(poster.get("pick"), "oldest").lower() or "oldest"
    if photo_pick not in {"oldest", "random"}:
        raise ValueError("poster.pick must be 'oldest' or 'random'")

    personas = []
    for i, item in enumerate(raw.get("personas") or []):
        pid = _as_str(item.get("id"))
        if not pid:
            raise ValueError(f"personas[{i}] needs an id")
        photos_dir = Path(_as_str(item.get("photos_dir"), f"media/personas/{pid}/photos"))
        used_dir = Path(_as_str(item.get("used_dir"), f"media/personas/{pid}/used"))
        if not photos_dir.is_absolute():
            photos_dir = (ROOT / photos_dir).resolve()
        if not used_dir.is_absolute():
            used_dir = (ROOT / used_dir).resolve()
        personas.append(
            Persona(
                id=pid,
                display_name=_as_str(item.get("display_name"), pid),
                photos_dir=photos_dir,
                used_dir=used_dir,
                voice=_as_str(item.get("voice"), "First person, casual, 18+ adult woman."),
                enabled=_as_bool(item.get("enabled"), True),
                subreddits=_as_str_list(item.get("subreddits")) or list(subreddits),
                fallback_captions=_as_str_list(item.get("fallback_captions")),
                reddit_profile=_as_str(item.get("reddit_profile"), "reddit_main") or "reddit_main",
                twitter_profile=_as_str(item.get("twitter_profile"), "twitter_main") or "twitter_main",
            )
        )

    logger.info(
        "Loaded %s styles and %s personas from %s (mode=%s graphic_level=%s)",
        len(styles),
        len(personas),
        config_path,
        mode,
        graphic_level,
    )
    return ContentConfig(
        styles=styles,
        subject=subject,
        hair=hair,
        eyes=eyes,
        body=body,
        details=details,
        quality=quality,
        framing=framing,
        photography=photography,
        negative_prompt=negative_prompt,
        graphic_level=graphic_level,
        graphic_levels=graphic_levels,
        images_always_explicit=images_always_explicit,
        require_nude=require_nude,
        image=image,
        subreddits=subreddits,
        sleep_min_seconds=sleep_min,
        sleep_max_seconds=sleep_max,
        path=config_path,
        variety=variety,
        mode=mode,
        photo_pick=photo_pick,
        personas=personas,
    )
