from pathlib import Path

import pytest

from media.photo_library import filename_hint, list_photos, mark_used, take_next_photo


def _touch_photo(folder: Path, name: str, mtime: int) -> Path:
    path = folder / name
    path.write_bytes(b"\x89PNG\r\n")
    Path(path).touch()
    import os
    os.utime(path, (mtime, mtime))
    return path


def test_list_and_oldest_pick(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "notes.txt").write_text("ignore me")
    _touch_photo(photos, "b.png", 200)
    _touch_photo(photos, "a.jpg", 100)
    names = [p.name for p in list_photos(photos)]
    assert names == ["a.jpg", "b.png"]
    assert take_next_photo(photos, pick="oldest").name == "a.jpg"


def test_mark_used(tmp_path):
    photos = tmp_path / "photos"
    used = tmp_path / "used"
    photos.mkdir()
    src = _touch_photo(photos, "shot.webp", 1)
    dest = mark_used(src, used)
    assert dest.exists()
    assert not src.exists()
    assert dest.parent == used


def test_empty_folder_errors(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    with pytest.raises(FileNotFoundError):
        take_next_photo(photos)


def test_filename_hint():
    assert filename_hint(Path("mirror-selfie.jpg")) == "mirror selfie"
    assert filename_hint(Path("IMG_1234.JPG")) == ""
    assert filename_hint(Path("x.png")) == ""


def test_real_config_photo_mode():
    from brain.content_config import load_content_config
    config = load_content_config()
    assert config.mode == "photos"
    assert config.enabled_personas()
    persona = config.enabled_personas()[0]
    assert persona.photos_dir.name == "photos"
    assert "first person" in persona.voice.lower() or "I," in persona.voice or "first person" in persona.voice.lower()
