import json

import pika
from loguru import logger

from .configuration import RabbitConfig
from .utils import setup_rabbitmq


class Expander(object):
    def expand(self, predicate: str):
        return [
            predicate,
            # predicate.title(),
            # predicate.upper(),
        ]


def main():
    expander = Expander()

    rabbitconfig = RabbitConfig()
    channel, connection = setup_rabbitmq(rabbitconfig)

    def callback(ch, method, properties, body):
        msg = json.loads(body)
        logger.info(f"Expanding: {msg}")
        try:
            for query in expander.expand(msg["predicate"]):
                msg2 = {**msg, "query": query}
                logger.debug(f"Expanded: {msg2}")
                channel.basic_publish(
                    exchange=rabbitconfig.exchange,
                    routing_key=rabbitconfig.scrape_key,
                    body=json.dumps(msg2).encode(),
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
