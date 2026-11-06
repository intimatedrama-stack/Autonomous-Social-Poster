import pytest

from brain.content_config import load_content_config
from brain.llm_client import LLMClient


SAMPLE = """
[subject]
description = "adult woman, mid-20s, auburn hair"

[look]
photography = "candid iphone snapshot"

[generation]
graphic_level = "suggestive"
negative_prompt = "blurry, child"

[image]
width = 256
height = 384
steps = 8
cfg_scale = 5.5
sampler = "DPM++ 2M"

[reddit]
subreddits = ["selfies", "pics"]

[schedule]
sleep_min_seconds = 10
sleep_max_seconds = 20

[[styles]]
id = "cafe"
name = "Cafe window"
enabled = true
topic = "drinking coffee by a window"
clothing = "knit sweater"
setting = "sunny cafe"
extra_sd_tags = "steam, bokeh"

[[styles]]
id = "gym"
name = "Gym"
enabled = false
topic = "finishing a workout"
"""


def test_load_real_content_toml():
    config = load_content_config()
    assert config.enabled_styles()
    style = config.pick_style()
    seed = config.prompt_seed(style)
    assert style.topic in seed
    assert set(config.graphic_levels) <= {"sfw", "suggestive", "explicit", "nsfw"}
    assert config.graphic_levels


def test_load_sample_and_prompt_seed(tmp_path):
    path = tmp_path / "content.toml"
    path.write_text(SAMPLE)
    config = load_content_config(path)

    assert [s.id for s in config.enabled_styles()] == ["cafe"]
    cafe = config.get_style("cafe")
    seed = config.prompt_seed(cafe)
    assert "adult woman, mid-20s, auburn hair" in seed
    assert "drinking coffee by a window" in seed
    assert "wearing knit sweater" in seed
    assert "in sunny cafe" in seed
    assert "candid iphone snapshot" in seed
    assert "steam, bokeh" in seed
    assert config.image.width == 256
    assert config.image.sampler == "DPM++ 2M"
    assert config.graphic_level == "suggestive"
    assert config.graphic_levels == ["suggestive"]

    gym = config.get_style("gym")
    assert gym.enabled is False
    with pytest.raises(KeyError):
        config.get_style("missing")


def test_pick_style_requires_enabled(tmp_path):
    path = tmp_path / "content.toml"
    path.write_text(
        SAMPLE.replace("enabled = true", "enabled = false")
    )
    config = load_content_config(path)
    with pytest.raises(ValueError, match="No enabled styles"):
        config.pick_style()


def test_invalid_graphic_level(tmp_path):
    path = tmp_path / "content.toml"
    path.write_text(SAMPLE.replace('graphic_level = "suggestive"', 'graphic_level = "whatever"'))
    with pytest.raises(ValueError, match="graphic_level"):
        load_content_config(path)


def test_slash_graphic_levels_and_nsfw(tmp_path):
    path = tmp_path / "content.toml"
    path.write_text(
        SAMPLE.replace(
            'graphic_level = "suggestive"',
            'graphic_level = "suggestive/explicit/nsfw"',
        )
    )
    config = load_content_config(path)
    assert config.graphic_levels == ["suggestive", "explicit", "nsfw"]
    assert config.graphic_level == "suggestive/explicit/nsfw"
    assert config.pick_graphic_level() in config.graphic_levels


def test_each_plan_is_unique_and_explicit(tmp_path):
    path = tmp_path / "content.toml"
    path.write_text(SAMPLE)
    config = load_content_config(path)
    keys = []
    plans = []
    for _ in range(8):
        plan = config.plan_generation(style_id="cafe", avoid_combo_keys=keys)
        keys.append(plan.combo_key)
        plans.append(plan)
    assert len(set(keys)) == 8
    assert len({p.seed for p in plans}) == 8
    assert all("explicit 18+ NSFW" in p.topic for p in plans)
    assert all(p.sd_prompt for p in plans)


def test_sd_prompt_puts_looks_and_nude_first():
    config = load_content_config()
    plan = config.plan_generation()
    prompt = plan.sd_prompt.lower()
    assert prompt.startswith("photorealistic") or "beautiful" in prompt.split(",")[0]
    assert "nude" in prompt or "naked" in prompt
    assert "full body" in prompt
    # uniqueness hashes must not pollute the image prompt
    assert ":" not in plan.sd_prompt.split(",")[0]


def test_llm_uses_graphic_level_and_style_lock():
    from unittest.mock import patch

    client = LLMClient(model="test-model")
    with patch("brain.llm_client.requests.post", side_effect=Exception("stop")) as post:
        client.generate_post_content(
            "topic",
            graphic_level="nsfw",
            style_lock="film grain, kodak portra",
            always_explicit=True,
            unique_key="abc123",
            avoid_scenes=["old bedroom scene"],
        )

    prompt = post.call_args[1]["json"]["prompt"]
    assert "NSFW" in prompt
    assert "film grain, kodak portra" in prompt
    assert "Never depict anyone under 18" in prompt
    assert "explicit 18+ NSFW" in prompt
    assert "abc123" in prompt
    assert "old bedroom scene" in prompt
