from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Dict, Iterator, List, Sequence, Tuple, TypedDict, Union

import pika
import tabulate as tabulate
from loguru import logger

from configuration import RabbitConfig
from utils import setup_rabbitmq


class Expander(object):
    def __init__(self, data_root: Union[str, Path], ngrams=None, ngrams_max=None):
        data_root = Path(data_root)
        predicates = Path.read_text(data_root / "vrd" / "predicates.txt").splitlines(
            keepends=False
        )

        self.ngrams = (
            Expander._load_ngrams(data_root, ngrams, predicates)
            if ngrams is not None
            else {}
        )
        self.ngrams_max = ngrams_max

    def expand(self, predicate: str) -> Iterator[Expander.ExpanderDict]:
        yield Expander.ExpanderDict(expansion="none", query=predicate)

        for n in self.ngrams:
            for freq, ngram in itertools.islice(
                self.ngrams[n][predicate], self.ngrams_max
            ):
                yield Expander.ExpanderDict(expansion=f"{n}gram", query=ngram)

    class ExpanderDict(TypedDict):
        expansion: str
        query: str

    @staticmethod
    def _load_ngrams(
        data_root: Path, ngrams: Sequence[int], predicates: Sequence[str]
    ) -> Dict[int, Dict[str, List[Tuple[int, str]]]]:
        result: Dict[int, Dict[str, List[Tuple[int, str]]]] = {}
        for n in ngrams:
            result[n] = {}
            for p in predicates:
                ngram_path = (
                    data_root
                    / "ngrams"
                    / "processed"
                    / f"{n}gram"
                    / f'{p.replace(" ", "_")}.txt'
                )
                with ngram_path.open() as f:
                    result[n][p] = [Expander._parse_ngram(line) for line in f]
        return result

    @staticmethod
    def _parse_ngram(line: str) -> Tuple[int, str]:
        freq, ngram = line.strip().split(maxsplit=1)
        return int(freq), ngram


def main():
    parser = argparse.ArgumentParser(description="Query expander")
    parser.add_argument("data_root", help="Data root", type=Path)
    parser.add_argument(
        "--ngrams",
        type=lambda s: [int(n) for n in s.split(",")],
        help="ngrams, e.g. 3,4,5",
        default=None,
    )
    parser.add_argument(
        "--ngrams-max",
        type=int,
        help="max ngram expansions",
        default=None,
    )

    subparsers = parser.add_subparsers(
        help="Subcommands", metavar="MODE", required=True
    )
    # Daemon mode
    parser_daemon = subparsers.add_parser(
        "daemon", help="Receive queries to and submit expansions from RabbitMQ"
    )
    parser_daemon.set_defaults(mode=daemon)

    # Manual mode
    parser_manual = subparsers.add_parser("manual", help="Manual expansion")
    parser_manual.add_argument("query", help="Query to expand")
    parser_manual.set_defaults(mode=manual)

    args = parser.parse_args()
    args.mode(args)


def manual(args):
    expander = Expander(args.data_root, args.ngrams, args.ngrams_max)
    expansions = list(exp.values() for exp in expander.expand(args.query))
    print(tabulate.tabulate(expansions, headers=["expansion", "query"]))
    print("Total:", len(expansions))


def daemon(args):
    expander = Expander(args.data_root, args.ngrams)

    rabbitconfig = RabbitConfig()
    channel, connection = setup_rabbitmq(rabbitconfig)

    def callback(ch, method, properties, body):
        msg_query = json.loads(body)
        logger.info(f"Expanding: {msg_query}")
        try:
            for expansion in expander.expand(msg_query["predicate"]):
                msg_exp = {**msg_query, **expansion}
                logger.debug(f"Expanded: {msg_exp}")
                channel.basic_publish(
                    exchange=rabbitconfig.exchange,
                    routing_key=rabbitconfig.scrape_key,
                    body=json.dumps(msg_exp).encode(),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            ch.basic_nack(delivery_tag=method.delivery_tag)
            logger.warning(f"Failed: {msg_query} {e}")

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
