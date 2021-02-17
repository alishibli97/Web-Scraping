import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def from_env(env_variable: str) -> Optional[str]:
    if env_variable in os.environ:
        return os.environ[env_variable]
    if f"{env_variable}_FILE" in os.environ:
        return Path(os.environ[f"{env_variable}_FILE"]).read_text().strip()
    return None


def env_field(env_variable: str, default: Any):
    def f():
        value = from_env(env_variable)
        if value is None:
            return default
        return type(default)(value)

    return field(default_factory=f)


@dataclass
class RabbitConfig(object):
    hostname: str = env_field("RABBITMQ_HOSTNAME", "localhost")
    port: int = env_field("RABBITMQ_PORT", 5672)
    user: str = env_field("RABBITMQ_DEFAULT_USER", "user")
    password: str = env_field("RABBITMQ_DEFAULT_PASS", "password")
    exchange: str = "tasks_exchange"
    expand_queue: str = "expand_queue"
    expand_key: str = "expand_key"
    scrape_queue: str = "scrape_queue"
    scrape_key: str = "scrape_key"


@dataclass
class MongoConfig(object):
    hostname: str = env_field("MONGO_HOSTNAME", "localhost")
    port: int = env_field("MONGO_PORT", 27017)
    user: str = env_field("MONGO_INITDB_ROOT_USERNAME", "root")
    password: str = env_field("MONGO_INITDB_ROOT_PASSWORD", "example")
    db: str = "webly"
    metadata_collection: str = "metadata"
    images_collection: str = "images"
