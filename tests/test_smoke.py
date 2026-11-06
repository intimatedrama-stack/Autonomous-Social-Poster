import json
import os
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from db.db_setup import DB_PATH, init_db
from brain.llm_client import LLMClient, OLLAMA_API_URL
from media.sd_client import StableDiffusionClient, SD_API_URL
from automation.trend_scraper import TrendScraper


def test_imports():
    import main
    import scripts.generate_test_post as generate_test_post
    import scripts.login_accounts as login_accounts
    from automation.browser_manager import BrowserManager
    from automation.reddit_poster import RedditPoster
    from automation.twitter_poster import TwitterPoster

    assert main is not None
    assert generate_test_post is not None
    assert login_accounts is not None
    assert BrowserManager is not None
    assert RedditPoster is not None
    assert TwitterPoster is not None


def test_db_init_and_schema():
    init_db()
    assert os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "posts" in tables
        assert "accounts" in tables
        posts_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(posts)")
        }
        assert {"id", "platform", "caption", "status", "media_path"} <= posts_cols
    finally:
        conn.close()


def test_llm_client_parses_json_response():
    client = LLMClient(model="test-model")
    fake_payload = {"caption": "hello from bed #selfie", "sd_prompt": "amateur photo"}
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"response": json.dumps(fake_payload)}

    with patch("brain.llm_client.requests.post", return_value=mock_resp) as post:
        result = client.generate_post_content("a cozy morning")

    assert result == fake_payload
    post.assert_called_once()
    args, kwargs = post.call_args
    assert args[0] == OLLAMA_API_URL
    assert kwargs["json"]["model"] == "test-model"
    assert kwargs["json"]["format"] == "json"


def test_llm_client_returns_none_on_connection_error():
    client = LLMClient()
    with patch("brain.llm_client.requests.post", side_effect=Exception("down")):
        assert client.generate_post_content("topic") is None


def test_sd_client_saves_image(tmp_path):
    client = StableDiffusionClient(output_dir=str(tmp_path))
    # 1x1 PNG
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
        "/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"images": [png_b64]}

    with patch("media.sd_client.requests.post", return_value=mock_resp) as post:
        path = client.generate_image("a test prompt", filename="unit.png")

    assert path is not None
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
    post.assert_called_once()
    assert post.call_args[0][0] == f"{SD_API_URL}/sdapi/v1/txt2img"
    assert post.call_args[1]["json"]["cfg_scale"] == 7.0
    assert post.call_args[1]["json"]["sampler_name"] == "Euler a"
    assert "seed" in post.call_args[1]["json"]


def test_sd_client_returns_none_on_error(tmp_path):
    client = StableDiffusionClient(output_dir=str(tmp_path))
    with patch("media.sd_client.requests.post", side_effect=Exception("down")):
        assert client.generate_image("prompt") is None


def test_trend_scraper_falls_back_when_reddit_blocks():
    scraper = TrendScraper()

    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 403
        resp.json.return_value = {}
        return resp

    with patch("automation.trend_scraper.requests.get", side_effect=fake_get):
        winner = scraper.get_best_subreddit(["gonewild", "selfies", "realgirls"])

    assert winner in {"gonewild", "selfies", "realgirls"}


def test_trend_scraper_picks_highest_active_subreddit():
    scraper = TrendScraper()
    calls = {"gonewild": 10, "selfies": 50, "realgirls": 20}

    def fake_get(url, headers=None, timeout=None):
        sub = url.split("/r/")[1].split("/")[0]
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"active_user_count": calls[sub]}}
        return resp

    with patch("automation.trend_scraper.requests.get", side_effect=fake_get):
        winner = scraper.get_best_subreddit(["gonewild", "selfies", "realgirls"])

    assert winner == "selfies"


def test_trend_scraper_twitter_fallback_on_browser_error():
    scraper = TrendScraper()
    with patch("automation.trend_scraper.BrowserManager") as bm_cls:
        bm = bm_cls.return_value
        bm.start.side_effect = Exception("no browser")
        trends = scraper.get_twitter_trends()

    assert isinstance(trends, list)
    assert len(trends) > 0
