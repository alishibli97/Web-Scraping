from __future__ import annotations

import argparse
import json

from loguru import logger

from .rabbit import declare_expand_queue, setup_rabbitmq


def parse_args():
    parser = argparse.ArgumentParser(description="Predicates")

    inputs = parser.add_argument_group("Input options")
    inputs.add_argument("predicates", nargs="+")

    output = parser.add_argument_group("Output options")
    output.add_argument(
        "--output",
        choices=["text", "json", "amqp"],
        default="text",
    )
    output.add_argument(
        "--amqp-url",
        type=str,
        help="url for amqp connections",
        default=None,
    )
    output.add_argument(
        "--amqp-pass-file",
        type=str,
        help="password file for amqp connections",
        default=None,
    )

    return parser.parse_args()


def stdout_output(d):
    print(d["predicate"], sep="\t")


def json_output(d):
    print(json.dumps(d))


def rabbit_output(channel):
    import pika

    queue = declare_expand_queue(channel)
    logger.info(f"Pushing predicates to queue `{queue}`")

    def output(msg):
        msg = json.dumps(msg)
        channel.basic_publish(
            exchange="webly",
            routing_key=queue,
            body=msg.encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        logger.debug(msg)

    return output


def main():
    args = parse_args()

    if args.output == "text":
        output = stdout_output
    elif args.output == "json":
        output = json_output
    elif args.output == "amqp":
        channel = setup_rabbitmq(args.amqp_url, args.amqp_pass_file)
        output = rabbit_output(channel)
    else:
        raise ValueError(f"Invalid --output: {args.output}")

    for p in args.predicates:
        if p.endswith(".txt"):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if len(line) > 0 and not line.startswith("#"):
                        output({"predicate": line})
        else:
            output({"predicate": p})


"""
python -m webly.predicates \
    --output amqp \
    --amqp-url amqp://user@localhost \
    --amqp-pass-file .secrets/rabbitmq_default_pass_file \
    drive eat drink data/vrd/predicates.txt
"""
if __name__ == "__main__":
    main()
