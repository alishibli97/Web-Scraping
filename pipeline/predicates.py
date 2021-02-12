import argparse
import json

import pika
from loguru import logger

from .configuration import RabbitConfig
from .utils import setup_rabbitmq


def main():
    parser = argparse.ArgumentParser(description="Image scraper")
    parser.add_argument("predicates", nargs="+")
    args = parser.parse_args()

    rabbitconfig = RabbitConfig()
    channel, connection = setup_rabbitmq(rabbitconfig)

    predicates = []
    for p in args.predicates:
        if p.endswith(".txt"):
            with open(p) as f:
                lines = map(str.strip, f)
                lines = filter(lambda l: len(l) > 0, lines)
                lines = filter(lambda l: not l.startswith("#"), lines)
                predicates.extend(lines)
        else:
            predicates.append(p)
    logger.info(f"Launching {len(predicates)} predicates")

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
