from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Iterator, NamedTuple, Sequence, Tuple, Union

from loguru import logger

from .rabbit import declare_expand_queue, declare_scrape_queue, setup_rabbitmq


class Expander(object):
    use_ngrams = False
    use_translation = False

    def __init__(
        self,
        ngrams_dir: Union[str, Path],
        ngrams: Sequence[int] = None,
        ngrams_max=None,
        languages: Sequence[str] = None,
    ):
        if not (
            (ngrams_dir is not None and ngrams is not None)
            or (ngrams_dir is None and ngrams is None and ngrams_max is None)
        ):
            raise ValueError(
                f"Invalid ngram configuration: {ngrams_dir=} {ngrams=} {ngrams_max=}"
            )

        if ngrams_dir is not None and ngrams is not None:
            self.use_ngrams = True
            self.ngrams = ngrams
            self.ngrams_dir = Path(ngrams_dir)
            self.ngrams_max = ngrams_max
            logger.info(
                f"Using ngrams {ngrams} from {ngrams_dir}"
                + (f" (max {ngrams_max} each)" if ngrams_max is not None else "")
            )

        if languages is not None:
            try:
                import googletrans

                translator = googletrans.Translator()
                translator.translate("hello", dest=languages[0])
                self.use_translation = True
                self.languages = languages
                self.translator = translator
                logger.info(f"Translating into {languages}")
            except Exception:
                logger.error("Translation unavailable")

    def expand(self, predicate: str) -> Iterator[ExpanderResult]:
        yield ExpanderResult(expansion="none", query=predicate)

        for lang, trans in self.iter_translations(predicate):
            yield ExpanderResult(expansion=f"translate({lang})", query=trans)

        for n, ngram in self.iter_ngrams(predicate):
            yield ExpanderResult(expansion=f"ngram({n})", query=ngram)

            for lang, ngram_trans in self.iter_translations(ngram):
                yield ExpanderResult(
                    expansion=f"ngram({n}),translate({lang})", query=ngram_trans
                )

    def iter_ngrams(self, predicate: str) -> Iterator[Tuple[int, str]]:
        if not self.use_ngrams:
            return

        for n in self.ngrams:
            ngram_path = (
                self.ngrams_dir / f"{n}gram" / f'{predicate.replace(" ", "_")}.txt'
            )
            if not ngram_path.is_file():
                logger.warning(f"Ngram file not found: {ngram_path}")
                return
            with open(ngram_path) as f:
                for line in itertools.islice(f, self.ngrams_max):
                    _, ngram = line.strip().split(maxsplit=1)
                    yield n, ngram

    def iter_translations(self, predicate: str) -> Iterator[Tuple[str, str]]:
        if not self.use_translation:
            return
        for lang in self.languages:
            trans = self.translator.translate(predicate, dest=lang)
            yield lang, trans


class ExpanderResult(NamedTuple):
    expansion: str
    query: str


def parse_args():
    parser = argparse.ArgumentParser(description="Query expander")

    io = parser.add_argument_group("Input/output options")
    io.add_argument(
        "--input",
        choices=["text", "json", "amqp"],
        default="text",
    )
    io.add_argument(
        "--output",
        choices=["text", "json", "amqp"],
        default="text",
    )
    io.add_argument(
        "--amqp-url",
        type=str,
        help="url for amqp connections",
        default=None,
    )
    io.add_argument(
        "--amqp-pass-file",
        type=str,
        help="password file for amqp connections",
        default=None,
    )

    ngrams = parser.add_argument_group("Ngram options")
    ngrams.add_argument(
        "--ngrams-dir",
        type=Path,
        help="ngram directory",
        default=None,
    )
    ngrams.add_argument(
        "--ngrams",
        choices=[2, 3, 4, 5],
        type=int,
        nargs="+",
        help="ngrams, e.g. 3 4 5",
        default=None,
    )
    ngrams.add_argument(
        "--ngrams-max",
        type=int,
        help="max ngram expansions",
        default=None,
    )
    translation = parser.add_argument_group("Translation options")
    translation.add_argument(
        "--languages",
        nargs="+",
        help="languages, e.g. se fr it",
        default=None,
    )
    return parser.parse_args()


def stdin_input_iterator():
    logger.info("Reading predicates from stdin")
    for line in sys.stdin:
        yield {"predicate": line.strip()}


def json_input_iterator():
    logger.info("Reading json predicates from stdin")
    for line in sys.stdin:
        yield json.loads(line)


def rabbit_input_iterator(channel):
    queue = declare_expand_queue(channel)
    logger.info(f"Receiving predicates from queue `{queue}`")

    try:
        for method, properties, body in channel.consume(queue=queue, auto_ack=False):
            try:
                yield json.loads(body)
                channel.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.exception("Error while processing msg", e)
                channel.basic_nack(delivery_tag=method.delivery_tag)
    except KeyboardInterrupt:
        logger.info("Interrupted: stop receiving messages")
    except Exception as e:
        logger.exception("Error while receiving msg", e)
    finally:
        channel.cancel()


def stdout_output(d):
    print(d["expansion"], d["query"], sep="\t")


def json_output(d):
    print(json.dumps(d))


def rabbit_output(channel):
    import pika

    queue = declare_scrape_queue(channel)
    logger.info(f"Pushing queries to queue `{queue}`")

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

    expander = Expander(
        ngrams_dir=args.ngrams_dir,
        ngrams=args.ngrams,
        ngrams_max=args.ngrams_max,
        languages=args.languages,
    )

    if args.input == "amqp" or args.output == "amqp":
        channel = setup_rabbitmq(args.amqp_url, args.amqp_pass_file)

    if args.input == "text":
        inputs = stdin_input_iterator()
    elif args.input == "json":
        inputs = json_input_iterator()
    elif args.input == "amqp":
        inputs = rabbit_input_iterator(channel)
    else:
        raise ValueError(f"Invalid --input: {args.input}")

    if args.output == "text":
        output = stdout_output
    elif args.output == "json":
        output = json_output
    elif args.output == "amqp":
        output = rabbit_output(channel)
    else:
        raise ValueError(f"Invalid --output: {args.output}")

    for d in inputs:
        for expansion, query in expander.expand(d["predicate"]):
            output({**d, "expansion": expansion, "query": query})


"""
python -m webly.expander \
    --ngrams 4 5 \
    --ngrams-dir data/ngrams/processed \
    --ngrams-max 2 \
    --languages fr it \
    --input text \
    --output json

python -m webly.expander \
    --ngrams 4 5 \
    --ngrams-dir data/ngrams/processed \
    --ngrams-max 2 \
    --languages fr it \
    --input amqp \
    --output amqp \
    --amqp-url amqp://user@localhost \
    --amqp-pass-file .secrets/rabbitmq_default_pass_file
"""
if __name__ == "__main__":
    main()
