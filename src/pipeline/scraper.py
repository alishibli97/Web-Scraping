from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from contextlib import ExitStack, suppress
from datetime import datetime
from itertools import islice
from typing import Dict, Iterator, Optional, TypedDict

import requests
from loguru import logger
from selenium import webdriver

from configuration import MongoConfig, RabbitConfig
from utils import setup_mongo, setup_rabbitmq

from .downloader import download_image


class ImageScraper(object):
    ENGINES = ("google", "yahoo", "flickr")

    def __init__(self, chrome):
        self.public_ip = get_chrome_ip_address(chrome)
        self.chrome = chrome

    def scrape(self, engine, query, num_images) -> Iterator[ScrapingDict]:
        """Main function to scrape"""
        if engine == "google":
            img_iterator = self.get_google_images(query)
        elif engine == "yahoo":
            img_iterator = self.get_yahoo_images(query)
        elif engine == "flickr":
            img_iterator = self.get_flickr_images(query)
        else:
            raise ValueError(f"Unknown engine: {engine}")

        yield from islice(img_iterator, num_images)

    def get_google_images(self, query: str) -> Iterator[ScrapingDict]:
        """Retrieve urls for images and captions from Google Images search engine"""

        def get_one(thumbnail):
            """Click on one thumbnail and try to get the http image source, fallback to url encoded"""
            self.chrome.execute_script("arguments[0].click();", thumbnail)
            time.sleep(0.5)

            caption = self.chrome.find_element_by_xpath(
                '//*[@id="Sva75c"]/div/div/div[3]/div[2]/c-wiz/div/div[1]/div[3]/div[2]/a'
            ).text
            img_element = self.chrome.find_element_by_xpath(
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
        self.chrome.get("https://www.google.com/search?" + query_params)

        result_index = 0
        while True:
            self.scroll_to_end()
            thumbnails = self.chrome.find_elements_by_css_selector("img.Q4LuWd")
            thumbnails = thumbnails[result_index:]
            if len(thumbnails) == 0:
                logger.debug("No more images after scrolling")
                return
            logger.debug(f"New images after scrolling: {len(thumbnails)}")

            for thumbnail in thumbnails:
                with logger.catch(Exception, reraise=False):
                    caption, url = get_one(thumbnail)
                    if url.endswith(".gif"):
                        logger.debug(f"Result {result_index} is .gif, skipping")
                        continue
                    yield ScrapingDict(
                        query=query,
                        public_ip=self.public_ip,
                        engine="google",
                        datetime_utc=datetime.utcnow(),
                        result_index=result_index,
                        caption=caption,
                        url=url,
                    )
                result_index += 1

    # TODO Simplify code similar to google images
    def get_yahoo_images(self, query) -> Iterator[ScrapingDict]:
        """Retrieve urls for images and captions from Yahoo Images search engine"""
        query_params = urllib.parse.urlencode(
            {
                "p": query,
                "ei": "UTF-8",
                "fr": "sfp",
            }
        )
        self.chrome.get(
            "https://images.search.yahoo.com/search/images;?" + query_params
        )

        # Accept cookie
        with suppress(Exception):
            self.chrome.find_element_by_xpath(
                '//*[@id="consent-page"]/div/div/div/div[2]/div[2]/form/button'
            ).click()

        start = 0
        prevLength = 0
        i = 0
        while True:
            self.scroll_to_end()

            html_list = self.chrome.find_element_by_xpath('//*[@id="sres"]')
            items = html_list.find_elements_by_tag_name("li")

            if len(items) == prevLength:
                print("Loaded all images")
                break
            prevLength = len(items)

            print(f"There are {len(items)} images")

            for content in items[start : len(items) - 1]:
                try:
                    self.chrome.execute_script("arguments[0].click();", content)
                    time.sleep(0.5)
                except Exception as e:
                    new_html_list = self.chrome.find_element_by_id("sres")
                    new_items = new_html_list.find_elements_by_tag_name("li")
                    item = new_items[i]
                    self.chrome.execute_script("arguments[0].click();", item)
                caption = self.chrome.find_element_by_class_name("title").text

                url = self.chrome.find_element_by_xpath('//*[@id="img"]')
                src = url.get_attribute("src")
                if src is not None and not src.endswith("gif"):
                    yield ScrapingDict(
                        query=query,
                        result_index=i,
                        url=url.get_attribute("src"),
                        caption=caption,
                        datetime_utc=datetime.utcnow(),
                        engine="yahoo",
                        public_ip=self.public_ip,
                    )
                i += 1
            start = len(items)

    # TODO Simplify code similar to google images
    def get_flickr_images(self, query) -> Iterator[ScrapingDict]:
        """Retrieve urls for images and captions from Flickr Images search engine"""
        query_params = urllib.parse.urlencode(
            {
                "text": query,
            }
        )
        self.chrome.get("https://www.flickr.com/search/?" + query_params)
        img_data = {}

        start = 0
        prevLength = 0
        i = 0
        waited = False
        while True:
            self.scroll_to_end()

            items = self.chrome.find_elements_by_xpath(
                "/html/body/div[1]/div/main/div[2]/div/div[2]/div"
            )

            if len(items) == prevLength:
                if not waited:
                    self.chrome.implicitly_wait(25)
                    waited = True
                else:
                    print("Loaded all images")
                    break
            prevLength = len(items)

            for item in items[start : len(items) - 1]:
                style = item.get_attribute("style")
                url = re.search(r'url\("//(.+?)"\);', style)
                if url:
                    url = "http://" + url.group(1)
                    caption = item.find_element_by_class_name(
                        "interaction-bar"
                    ).get_attribute("title")
                    caption = caption[: re.search(r"\bby\b", caption).start()].strip()

                    yield ScrapingDict(
                        query=query,
                        result_index=i,
                        url=url,
                        caption=caption,
                        datetime_utc=datetime.utcnow(),
                        engine="flickr",
                        public_ip=self.public_ip,
                    )
                i += 1
            start = len(items)
        return img_data

    def scroll_to_end(self):
        """Scroll to end of page"""
        self.chrome.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)


class ScrapingDict(TypedDict, total=False):
    predicate: str
    engine: str
    query: str
    result_index: int
    caption: str
    url: str
    public_ip: Optional[Dict[str, str]]
    datetime_utc: datetime


def create_chrome_driver(chrome=None, chrome_binary=None, chrome_driver=None):
    if chrome is None:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.headless = False
        if chrome_binary is not None:
            chrome_options.binary_location = chrome_binary
        kwargs = {}
        if chrome_driver is not None:
            kwargs["executable_path"] = chrome_driver
        driver = webdriver.Chrome(options=chrome_options, **kwargs)
    else:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        if "TOKEN" in os.environ:
            chrome_options.set_capability("browserless.token", os.environ["TOKEN"])
        driver = webdriver.Remote(
            command_executor=chrome,
            desired_capabilities=chrome_options.to_capabilities(),
        )
    logger.info(f"Started Chrome ({chrome})")
    return driver


def get_public_ip_address() -> Optional[Dict[str, str]]:
    """Read the public IP address of the host"""
    response = requests.get("http://ip-api.com/json/?fields=57625")
    try:
        response = response.json()
        if response["status"] != "success":
            logger.warning(f"Could not determine IP address: {response.pop('message')}")
            return None
        else:
            response["ip"] = response["query"]
            del response["status"], response["query"]
            return response
    except ValueError:
        logger.warning("Could not determine IP address: request failed")
        return None


def get_chrome_ip_address(chrome) -> Optional[Dict[str, str]]:
    try:
        chrome.get("http://ip-api.com/json/?fields=57625")
        response = json.loads(chrome.find_element_by_tag_name("pre").text)
        if response.pop("status") != "success":
            raise RuntimeError(response["message"])
        response["ip"] = response.pop("query")
        return response
    except Exception as e:
        logger.warning(f"Could not determine IP address: {e}")
        return None


@logger.catch(reraise=False, onerror=lambda _: sys.exit(1))
def main():
    parser = argparse.ArgumentParser(description="Image scraper")
    subparsers = parser.add_subparsers(
        help="Subcommands", metavar="MODE", required=True
    )

    # Common options
    group = parser.add_argument_group("Chrome options")
    group.add_argument(
        "--chrome",
        help="Remote Chrome url, e.g. 'http://localhost:3000/webdriver'. Will use a local process if absent.",
        default=None,
    )
    group.add_argument(
        "--chrome-binary", help="Only needed for local Chrome", default=None
    )
    group.add_argument(
        "--chrome-driver", help="Only needed for local Chrome", default=None
    )

    group = parser.add_argument_group("Saving options")
    group.add_argument("--out-dir", default="images")

    # Daemon mode
    parser_daemon = subparsers.add_parser(
        "daemon", help="Receive queries from RabbitMQ, save images to MongoDB"
    )
    parser_daemon.add_argument("num_images", help="Max number of images", type=int)
    parser_daemon.set_defaults(mode=daemon)

    # Manual mode
    parser_manual = subparsers.add_parser("manual", help="Manual query")
    parser_manual.add_argument(
        "engine", choices=ImageScraper.ENGINES, help="Search engine"
    )
    parser_manual.add_argument("query", help="Query to search for")
    parser_manual.add_argument("num_images", help="Max number of images", type=int)
    parser_manual.set_defaults(mode=manual)

    args = parser.parse_args()
    args.mode(args)


def daemon(args):
    def callback(ch, method, properties, body):
        msg = json.loads(body)
        logger.info(f"Scraping: {msg['query']}")
        try:
            for engine in scraper.ENGINES:
                for img_dict in scraper.scrape(engine, msg["query"], args.num_images):
                    logger.debug(
                        f"Scraped: {img_dict['engine']} {img_dict['query']} {img_dict['result_index']}"
                    )
                    metadata_collection.insert_one({**msg, **img_dict})
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            ch.basic_nack(delivery_tag=method.delivery_tag)
            logger.warning(f"Failed: {msg} {e}")

    with ExitStack() as stack:
        mongoconfig = MongoConfig()
        mongoclient, metadata_collection = setup_mongo(mongoconfig)
        stack.enter_context(mongoclient)

        rabbitconfig = RabbitConfig()
        channel, connection = setup_rabbitmq(rabbitconfig)
        stack.enter_context(connection)
        stack.enter_context(channel)

        chrome = create_chrome_driver(
            args.chrome, args.chrome_binary, args.chrome_driver
        )
        stack.enter_context(chrome)
        scraper = ImageScraper(chrome)

        try:
            logger.info("Waiting for queries")
            channel.basic_consume(
                queue=rabbitconfig.scrape_queue, on_message_callback=callback
            )
            channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Bye")


def manual(args):
    with ExitStack() as stack:
        chrome = create_chrome_driver(
            args.chrome, args.chrome_binary, args.chrome_driver
        )
        stack.enter_context(chrome)
        scraper = ImageScraper(chrome)

        for img_dict in scraper.scrape(args.engine, args.query, args.num_images):
            img_json = {
                **img_dict,
                "datetime_utc": img_dict["datetime_utc"].isoformat(),
                "url": img_dict["url"]
                if img_dict["url"].startswith("http")
                else img_dict["url"][:30],
            }
            logger.info(f"Scraped:\n{json.dumps(img_json,indent=2)}")
            try:
                img_dict["predicate"] = img_dict["query"]
                path = download_image(img_dict, args.out_dir)
                logger.info(f"Saved: {path}")
            except Exception as e:
                logger.warning(f"Image download failed: {e}")


if __name__ == "__main__":
    main()