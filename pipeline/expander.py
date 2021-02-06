import json
import random
import time

import pika
from loguru import logger

import rabbitconfig


class Expander(object):
    def __init__(self):
        logger.info("Expander created")

    def expand(self, predicate: str):
        if random.random() < 0.1:
            raise RuntimeError("Expansion error")
        time.sleep(2 * random.random())
        return [
            predicate,
            predicate.title(),
            predicate.upper(),
        ]


def main():
    expander = Expander()

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
            for query in expander.expand(msg["predicate"]):
                msg2 = {**msg, "query": query}
                logger.info(f"Expanded: {msg2}")
                channel.basic_publish(
                    exchange=rabbitconfig.exchange,
                    routing_key=rabbitconfig.scrape_key,
                    body=json.dumps(msg2),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            ch.basic_nack(delivery_tag=method.delivery_tag)
            logger.warning(f"Failed: {msg} {e}")

    try:
        channel.basic_consume(
            queue=rabbitconfig.expand_queue, on_message_callback=callback
        )
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Bye")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
