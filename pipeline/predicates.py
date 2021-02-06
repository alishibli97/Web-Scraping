import json
from itertools import product

import pika
from loguru import logger

import rabbitconfig


def main():
    predicates = map(
        "-".join,
        product(["hello", "hey"], ["world", "planet"], map(str, range(4))),
    )

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=rabbitconfig.hostname,
            port=rabbitconfig.port,
            credentials=pika.PlainCredentials(rabbitconfig.user, rabbitconfig.password),
        )
    )
    channel = connection.channel()
    channel.exchange_declare(exchange=rabbitconfig.exchange, exchange_type="direct")

    channel.queue_declare(queue=rabbitconfig.expand_queue, durable=True)
    channel.queue_bind(
        exchange=rabbitconfig.exchange,
        queue=rabbitconfig.expand_queue,
        routing_key=rabbitconfig.expand_key,
    )

    for predicate in predicates:
        channel.basic_publish(
            exchange=rabbitconfig.exchange,
            routing_key=rabbitconfig.expand_key,
            body=json.dumps({"predicate": predicate}).encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        logger.info(f"Predicate: {predicate}")
    connection.close()


if __name__ == "__main__":
    main()
