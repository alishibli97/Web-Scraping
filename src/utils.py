import pika
from loguru import logger
from pymongo import MongoClient


def setup_rabbitmq(rabbitconfig):
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

    logger.info("Connected to RabbitMQ")
    return channel, connection


def setup_mongo(mongoconfig):
    client = MongoClient(
        host=mongoconfig.hostname,
        port=mongoconfig.port,
        username=mongoconfig.user,
        password=mongoconfig.password,
    )
    db = client[mongoconfig.db]
    metadata_collection = db[mongoconfig.collection]
    db.command("collstats", mongoconfig.collection)
    logger.info("Connected to MongoDB")
    return client, metadata_collection
