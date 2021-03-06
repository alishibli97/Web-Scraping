import argparse
import base64
import io
import random
from pathlib import Path
from typing import Any, Mapping, Union

import requests
from loguru import logger
from PIL import Image

from .mongo import setup_mongo

user_agents = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Mobile Safari/537.36",
    "User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:85.0) Gecko/20100101 Firefox/85.0",
]


def download_image(img_dict: Mapping[str, Any], path: Union[str, Path], force=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file() and not force:
        return path

    if img_dict["url"].startswith("http"):
        response = requests.get(
            img_dict["url"],
            headers={"User-Agent": random.choice(user_agents)},
            timeout=10,
        )
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content))
        img = img.convert("RGB")
        with path.open("wb") as f:
            img.save(f, "JPEG", quality=95)
    elif img_dict["url"].startswith("data"):
        base64_img = img_dict["url"].split(",")[1]
        img = Image.open(io.BytesIO(base64.b64decode(base64_img)))
        img = img.convert("RGB")
        with path.open("wb") as f:
            img.save(f, "JPEG", quality=95)
    else:
        raise ValueError(f"Invalid image url: {img_dict['url']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Scraper")

    inputs = parser.add_argument_group("Input options")
    inputs.add_argument(
        "--mongo-url", type=str, help="url for database connections", required=True
    )
    inputs.add_argument(
        "--mongo-pass-file",
        type=str,
        help="password file for database connections",
        required=True,
    )

    output = parser.add_argument_group("Output options")
    output.add_argument("--output-dir", type=Path, required=True)

    return parser.parse_args()


def main():
    args = parse_args()
    args.output_dir.mkdir(exist_ok=True, parents=True)
    collection = setup_mongo(args.mongo_url, args.mongo_pass_file)

    for img_dict in collection.find():
        try:
            path = args.output_dir / f'{img_dict["_id"]}.jpg'
            if path.is_file():
                logger.info(f"Existing: {path}")
            else:
                download_image(img_dict, path)
                logger.info(f"Saved: {path}")
        except Exception as e:
            logger.warning(f"Image download failed: {e}")

"""
python -m webly.downloader \
    --mongo-url mongodb://user@localhost \
    --mongo-pass-file .secrets/mongo_initdb_root_password \
    --output-dir images
"""
if __name__ == "__main__":
    main()
