from pathlib import Path
from typing import Optional, Union

from loguru import logger


def setup_rabbitmq(url: str, pass_file: Optional[Union[str, Path]] = None):
    import pika

    logger.info(f"RabbitMQ connecting to: {url}")

    if pass_file is not None:
        pwd = Path(pass_file).read_text().strip()
        url = url.replace("@", f":{pwd}@")

    connection = pika.BlockingConnection(pika.URLParameters(url))

    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)
    channel.exchange_declare(exchange="webly", exchange_type="direct")

    return channel


def declare_expand_queue(channel):
    channel.queue_declare(queue="expand", durable=True)
    channel.queue_bind(
        exchange="webly",
        queue="expand",
        routing_key="expand",
    )
    return "expand"


def declare_scrape_queue(channel):
    channel.queue_declare(queue="scrape", durable=True)
    channel.queue_bind(
        exchange="webly",
        queue="scrape",
        routing_key="scrape",
    )
    return "scrape"
