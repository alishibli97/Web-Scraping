# Scraping Pipeline

1. Create folder `.secrets` and setup MongoDB and RabbitMQ credentials:
   ```bash
   cp -r .secrets_example .secrets
   # Edit files in .secrets
   export RABBITMQ_DEFAULT_USER_FILE=.secrets/rabbitmq_default_user_file
   export RABBITMQ_DEFAULT_PASS_FILE=.secrets/rabbitmq_default_pass_file
   export MONGO_INITDB_ROOT_USERNAME_FILE=.secrets/mongo_initdb_root_username
   export MONGO_INITDB_ROOT_PASSWORD_FILE=.secrets/mongo_initdb_root_password
   ```

2. Start all containers:
   ```bash
   docker-compose up -d
   docker-compose ps
   ```

3. Launch one or more of the expander and scraper processes:
   ```bash
   python -m pipeline.expander
   python -m pipeline.scraper daemon 40
   ```

4. Launch a process to generate predicates
   ```bash
   python predicates.py 'path/to/predicates.txt' 'some pred' 'another pred'
   ```
   
5. Kill expander and scraper processes, then stop containers:
   ```bash
   docker-compose stop
   ```

![Pipeline example](pipeline-example.png)

Monitoring:
- [RabbitMQ queues](http://localhost:15672/)
- [MongoDB documents](http://localhost:8081/)

Test queries manually:
```bash
python -m scraper manual google driving 100
```