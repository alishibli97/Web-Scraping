import json
import random
import time
from typing import Dict, Tuple, Iterator

import bson
import pika
from loguru import logger
from pymongo import MongoClient

import mongoconfig
import rabbitconfig


class Scraper(object):
    def __init__(self):
        logger.info("Scraper created")

    def scrape(self, query: str) -> Iterator[Tuple[Dict[str, str], bytes]]:
        if random.random() < 0.1:
            raise RuntimeError("Scraping error")
        for i in range(random.randint(0, 4)):
            time.sleep(random.random())
            meta = {"url": f"http://{query}.com/{i}", "browser": "chrome"}
            img = random.randbytes(128)
            yield meta, img


def main():
    scraper = Scraper()

    client = MongoClient(
        host=mongoconfig.hostname,
        port=mongoconfig.port,
        username=mongoconfig.user,
        password=mongoconfig.password,
    )
    db = client[mongoconfig.db]
    metadata_collection = db[mongoconfig.metadata_collection]
    images_collection = db[mongoconfig.images_collection]

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=rabbitconfig.hostname,
            port=rabbitconfig.port,
            credentials=pika.PlainCredentials(rabbitconfig.user, rabbitconfig.password),
        )
    )
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)
    channel.exchange_declare(exchange=rabbitconfig.exchange, exchange_type="direct")

    channel.queue_declare(queue=rabbitconfig.expand_queue, durable=True)
    channel.queue_bind(
        exchange=rabbitconfig.exchange,
        queue=rabbitconfig.expand_queue,
        routing_key=rabbitconfig.expand_key,
    )

    channel.queue_declare(queue=rabbitconfig.scrape_queue, durable=True)
    channel.queue_bind(
        exchange=rabbitconfig.exchange,
        queue=rabbitconfig.scrape_queue,
        routing_key=rabbitconfig.scrape_key,
    )

    def callback(ch, method, properties, body):
        msg = json.loads(body)
        try:
            for meta, img in scraper.scrape(msg["query"]):
                msg2 = {**msg, **meta}
                logger.info(f"Scraped: {msg2}")
                _id = metadata_collection.insert_one(msg2).inserted_id
                images_collection.insert_one({"_id": _id, "img": bson.Binary(img)})
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            ch.basic_nack(delivery_tag=method.delivery_tag)
            logger.warning(f"Failed: {msg} {e}")

    try:
        channel.basic_consume(
            queue=rabbitconfig.scrape_queue, on_message_callback=callback
        )
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Bye")
    finally:
        connection.close()
        client.close()


if __name__ == "__main__":
    main()
