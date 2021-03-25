from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import Dict, Iterator

from loguru import logger
from selenium import webdriver

from webly.mongo import setup_mongo

from .rabbit import declare_scrape_queue, setup_rabbitmq


def parse_args():
    parser = argparse.ArgumentParser(description="Scraper")

    inputs = parser.add_argument_group("Input options")
    inputs.add_argument(
        "--input",
        choices=["text", "json", "amqp"],
        default="text",
    )
    inputs.add_argument(
        "--amqp-url",
        type=str,
        help="url for amqp connections",
        default=None,
    )
    inputs.add_argument(
        "--amqp-pass-file",
        type=str,
        help="password file for amqp connections",
        default=None,
    )

    output = parser.add_argument_group("Output options")
    output.add_argument(
        "--output",
        choices=["text", "json", "mongo"],
        default="json",
    )
    output.add_argument(
        "--mongo-url",
        type=str,
        help="url for database connections",
        default=None,
    )
    output.add_argument(
        "--mongo-pass-file",
        type=str,
        help="password file for database connections",
        default=None,
    )

    scraping = parser.add_argument_group("Scraping options")
    scraping.add_argument(
        "--engines",
        choices=["google", "yahoo", "flickr"],
        help="engines, e.g. google yahoo",
        nargs="+",
        required=True,
    )
    scraping.add_argument(
        "--num-images",
        type=int,
        help="max number of images per query",
        default=20,
    )

    chrome = parser.add_argument_group("Chrome options")
    chrome.add_argument(
        "--chrome-url",
        type=str,
        help="Remote Chrome url, e.g. 'http://localhost:3000/webdriver'. Will use a local process if absent.",
        default=None,
    )
    chrome.add_argument(
        "--chrome-token-file",
        type=str,
        help="Only needed for remote Chrome",
        default=None,
    )
    chrome.add_argument(
        "--chrome-binary", type=str, help="Only needed for local Chrome", default=None
    )
    chrome.add_argument(
        "--chrome-driver", type=str, help="Only needed for local Chrome", default=None
    )

    return parser.parse_args()


def stdin_input_iterator():
    logger.info("Reading queries from stdin")
    for line in sys.stdin:
        yield {"query": line.strip()}


def json_input_iterator():
    logger.info("Reading json queries from stdin")
    for line in sys.stdin:
        yield json.loads(line)


def rabbit_input_iterator(channel):
    queue = declare_scrape_queue(channel)
    logger.info(f"Receiving queries from queue `{queue}`")

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
    print(
        d["engine"],
        d["query"],
        d["result_index"],
        d["caption"],
        d["url"][:20] if d["url"].startswith("data:image/") else d["url"],
        sep="\t",
    )


def json_output(d):
    d["datetime_utc"] = str(d["datetime_utc"])
    print(json.dumps(d))


def chrome_helper(
    chrome_url=None, chrome_token_file=None, chrome_binary=None, chrome_driver=None
):
    if chrome_url is None:
        logger.debug(f"Using local Chrome")
        chrome_options = webdriver.ChromeOptions()
        chrome_options.headless = False
        if chrome_binary is not None:
            chrome_options.binary_location = chrome_binary
        kwargs = {}
        if chrome_driver is not None:
            kwargs["executable_path"] = chrome_driver

        def create_driver():
            return webdriver.Chrome(options=chrome_options, **kwargs)

    else:
        logger.debug(f"Using remote Chrome ({chrome_url})")
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        token = Path(chrome_token_file).read_text().strip().replace("TOKEN=", "", 1)
        chrome_options.set_capability("browserless.token", token)
        capabilities = chrome_options.to_capabilities()

        def create_driver():
            return webdriver.Remote(
                command_executor=chrome_url,
                desired_capabilities=capabilities,
            )

    return create_driver


def get_ip_info(driver) -> Dict[str, str]:
    driver.get("http://ip-api.com/json/?fields=57625")
    response = json.loads(driver.find_element_by_tag_name("pre").text)
    if response.pop("status") != "success":
        raise RuntimeError(response["message"])
    response["ip"] = response.pop("query")
    return response


def get_google_images(driver, query) -> Iterator[Dict]:
    """Scrape image urls and captions from Google Images"""

    def get_one(thumbnail):
        """Click on one thumbnail and try to get the http image source, fallback to url encoded"""
        driver.execute_script("arguments[0].click();", thumbnail)
        time.sleep(0.5)

        caption = driver.find_element_by_xpath(
            '//*[@id="Sva75c"]/div/div/div[3]/div[2]/c-wiz/div/div[1]/div[3]/div[2]/a'
        ).text
        img_element = driver.find_element_by_xpath(
            '//*[@id="Sva75c"]/div/div/div[3]/div[2]/c-wiz/div/div[1]/div[1]/div/div[2]/a/img'
        )
        url = img_element.get_attribute("src")
        return caption, url

    query_params = urllib.parse.urlencode(
        {
            "safe": "off",
            "tbm": "isch",
            "source": "hp",
            "q": query,
            "gs_l": "img",
        }
    )
    driver.get("https://www.google.com/search?" + query_params)
    query_datetime = datetime.utcnow()

    result_index = 0
    while True:
        scroll_to_end(driver)
        thumbnails = driver.find_elements_by_css_selector("img.Q4LuWd")
        thumbnails = thumbnails[result_index:]
        if len(thumbnails) == 0:
            logger.debug("No more images after scrolling")
            return
        logger.trace(f"New images after scrolling: {len(thumbnails)}")

        for thumbnail in thumbnails:
            with logger.catch(Exception, reraise=False):
                caption, url = get_one(thumbnail)
                if url.endswith(".gif"):
                    logger.debug(f"Result {result_index} is .gif, skipping")
                    continue
                yield {
                    "query": query,
                    "datetime_utc": query_datetime,
                    "result_index": result_index,
                    "caption": caption,
                    "url": url,
                }
            result_index += 1


def get_yahoo_images(driver, query):
    raise NotImplementedError


def get_flickr_images(driver, query):
    raise NotImplementedError


def scroll_to_end(driver):
    """Scroll to end of page"""
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)


def main():
    args = parse_args()

    create_driver = chrome_helper(
        args.chrome_url,
        args.chrome_token_file,
        args.chrome_binary,
        args.chrome_driver,
    )
    try:
        driver = create_driver()
        with driver:
            ip_info = get_ip_info(driver)
        logger.info(f"IP info: {ip_info}")
    except Exception as e:
        logger.exception("Could not get IP info", e)
        exit(1)

    if args.input == "text":
        inputs = stdin_input_iterator()
    elif args.input == "json":
        inputs = json_input_iterator()
    elif args.input == "amqp":
        channel = setup_rabbitmq(args.amqp_url, args.amqp_pass_file)
        inputs = rabbit_input_iterator(channel)
    else:
        raise ValueError(f"Invalid --input: {args.input}")

    if args.output == "text":
        output = stdout_output
    elif args.output == "json":
        output = json_output
    elif args.output == "mongo":
        collection = setup_mongo(args.mongo_url, args.mongo_pass_file)
        output = collection.insert_one
    else:
        raise ValueError(f"Invalid --output: {args.output}")

    for d in inputs:
        driver = create_driver()
        with driver:
            for engine in args.engines:
                scraping_fn = {
                    "google": get_google_images,
                    "yahoo": get_yahoo_images,
                    "flickr": get_flickr_images,
                }[engine]
                for res in islice(scraping_fn(driver, d["query"]), args.num_images):
                    output({**d, **res, "engine": engine, "public_ip": ip_info})
                logger.debug(f'Scraped {engine}: {d["query"]}')


"""
python -m webly.scraper \
    --engines google yahoo flickr \
    --chrome-url http://localhost:3000/webdriver \
    --chrome-token-file .secrets/chrome_token \
    --input amqp \
    --output mongo \
    --amqp-url amqp://user@localhost \
    --amqp-pass-file .secrets/rabbitmq_default_pass_file \
    --mongo-url mongodb://user@localhost \
    --mongo-pass-file .secrets/mongo_initdb_root_password
    
python -m webly.scraper \
    --engines google yahoo flickr \
    --chrome-url http://localhost:3000/webdriver \
    --chrome-token-file .secrets/chrome_token \
    --input text \
    --output text
"""
if __name__ == "__main__":
    main()
