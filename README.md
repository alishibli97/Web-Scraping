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
   
3. Set python path:
   ```bash
   export "PYTHONPATH=${PYTHONPATH:+${PYTHONPATH}:}$(realpath ./src)"
   ```

4. Launch a process to generate predicates
   ```bash
   export RABBITMQ_DEFAULT_USER_FILE=.secrets/rabbitmq_default_user_file
   export RABBITMQ_DEFAULT_PASS_FILE=.secrets/rabbitmq_default_pass_file
   python -m pipeline.predicates data/vrd/predicates.txt
   ```

5. Launch one or more of the expander processes:
   ```bash
   export RABBITMQ_DEFAULT_USER_FILE=.secrets/rabbitmq_default_user_file
   export RABBITMQ_DEFAULT_PASS_FILE=.secrets/rabbitmq_default_pass_file                                                                        
   python -m pipeline.expander --ngrams=3,4,5 --ngrams-max 10 ./data daemon
   ```

6. Launch one or more scraper processes:
   ```bash
   export RABBITMQ_DEFAULT_USER_FILE=.secrets/rabbitmq_default_user_file
   export RABBITMQ_DEFAULT_PASS_FILE=.secrets/rabbitmq_default_pass_file
   export MONGO_INITDB_ROOT_USERNAME_FILE=.secrets/mongo_initdb_root_username
   export MONGO_INITDB_ROOT_PASSWORD_FILE=.secrets/mongo_initdb_root_password
   source .secrets/chrome_token && export TOKEN
   python -m pipeline.scraper --chrome 'http://localhost:3000/webdriver' daemon 40
   ```
   
7. Kill expander and scraper processes, then stop containers:
   ```bash
   docker-compose stop
   ```
   
8. Download images
   ```bash
   export MONGO_INITDB_ROOT_USERNAME_FILE=.secrets/mongo_initdb_root_username
   export MONGO_INITDB_ROOT_PASSWORD_FILE=.secrets/mongo_initdb_root_password
   python -m pipeline.downloader 
   ```

![Pipeline example](pipeline-example.png)

Monitoring:
- [RabbitMQ queues](http://localhost:15672/)
- [MongoDB documents](http://localhost:8081/)

Test queries manually:
```bash
python -m pipeline.scraper manual google driving 100
```