# Scraping Pipeline

1. Create folder `.secrets` and setup MongoDB, RabbitMQ, and Chrome credentials:
   ```bash
   cp -r .secrets_example .secrets 
   ```

2. Start all containers:
   ```bash
   docker-compose up -d
   docker-compose ps
   ```
   
3. Install package:
   ```bash
   pip install --editable '.'
   ```

4. Launch a process to generate predicates
   ```bash
   python -m webly.predicates \
       --output amqp \
       --amqp-url amqp://user@localhost \
       --amqp-pass-file .secrets/rabbitmq_default_pass_file \
       data/vrd/predicates.txt
   ```

5. Launch one or more of the expander processes:
   ```bash
   python -m webly.expander \
       --ngrams 4 5 \
       --ngrams-dir data/ngrams/processed \
       --ngrams-max 2 \
       --languages fr it \
       --input amqp \
       --output amqp \
       --amqp-url amqp://user@localhost \
       --amqp-pass-file .secrets/rabbitmq_default_pass_file
   ```

6. Launch one or more scraper processes:
   ```bash
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
   ```
   
7. Kill expander and scraper processes, then stop containers:
   ```bash
   docker-compose stop
   ```
   
8. Download images
   ```bash
   python -m webly.downloader \
       --mongo-url mongodb://user@localhost \
       --mongo-pass-file .secrets/mongo_initdb_root_password \
       --output-dir images 
   ```

Monitoring:
- [RabbitMQ queues](http://localhost:15672/)
- [MongoDB documents](http://localhost:8081/)

Test queries manually (input from stdin):
```bash
python -m webly.scraper \
    --engines google yahoo flickr \
    --chrome-url http://localhost:3000/webdriver \
    --chrome-token-file .secrets/chrome_token \
    --input text \
    --output text
```