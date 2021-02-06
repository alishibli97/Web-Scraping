# Pipeline

1. Start all containers from the top directory as:
   ```bash
   docker-compose up -d
   ```
2. Launch one or more of the expander and scraper processes:
   ```bash
   python expander.py
   python scraper.py
   ```
3. Launch a process to generate predicates
   ```bash
   python predicates.py
   ```
   
Default credentials are set in:
- [`../.secrets`](../.secrets)
- [`./mongoconfig.py`](./mongoconfig.py)
- [`./rabbitconfig.py`](./rabbitconfig.py)

Monitoring:
- [RabbitMQ queues](http://localhost:15672/)
- [MongoDB documents](http://localhost:8081/)