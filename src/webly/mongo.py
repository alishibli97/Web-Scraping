from pathlib import Path
from typing import Optional, Union

from loguru import logger


def setup_mongo(url: str, pass_file: Optional[Union[str, Path]] = None):
    from pymongo import MongoClient

    logger.info(f"MongoDB connecting to: {url}")

    kwargs = {}
    if pass_file is not None:
        pwd = Path(pass_file).read_text().strip()
        kwargs = {"password": pwd}

    client = MongoClient(url, **kwargs)
    db = client["webly"]
    collection = db["metadata"]

    # Test connection
    db.command("collstats", "metadata")
    logger.info("Connected to MongoDB")

    return collection
