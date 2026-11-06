import logging
import random
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class PhotoPick:
    path: Path
    persona_id: str
    hint: str


def list_photos(photos_dir: Path) -> list[Path]:
    if not photos_dir.is_dir():
        return []
    photos = [
        path for path in photos_dir.iterdir()
        if path.is_file() and path.suffix.lower() in PHOTO_EXTS
    ]
    return sorted(photos, key=lambda path: (path.stat().st_mtime, path.name))


def filename_hint(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    letters = sum(ch.isalpha() for ch in stem)
    if letters < 4 or stem.lower().startswith("img") or stem.lower().startswith("dsc"):
        return ""
    return stem


def take_next_photo(photos_dir: Path, pick: str = "oldest") -> Path:
    photos = list_photos(photos_dir)
    if not photos:
        raise FileNotFoundError(
            f"No unused photos in {photos_dir}. Drop .jpg/.png/.webp files you have rights to use."
        )
    if pick == "random":
        return random.choice(photos)
    return photos[0]


def mark_used(photo: Path, used_dir: Path) -> Path:
    used_dir.mkdir(parents=True, exist_ok=True)
    dest = used_dir / photo.name
    if dest.exists():
        dest = used_dir / f"{photo.stem}_{int(time.time())}{photo.suffix}"
    shutil.move(str(photo), str(dest))
    logger.info("Moved posted photo to %s", dest)
    return dest
