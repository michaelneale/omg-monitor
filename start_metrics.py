#!/usr/bin/env python

import sys
import multiprocessing
import logging
import logging.handlers
import json
from monitor import metrics_monitor
from utils import pingdom # Pingdom API wrapper
import redis
import os

# Connect to redis server
_REDIS_SERVER = redis.Redis("localhost")

# Use logging
logger = logging.getLogger(__name__)
handler = logging.handlers.RotatingFileHandler(os.environ['LOG_DIR']+"/start.log",
                                                maxBytes=1024*1024,
                                                backupCount=4,
                                                )

formatter = logging.Formatter('[%(levelname)s/%(processName)s][%(asctime)s] %(name)s %(message)s')
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Multiprocessing logger
multiprocessing.log_to_stderr(logging.DEBUG)

# Test the redis server
try:
    response = _REDIS_SERVER.client_list()
except redis.ConnectionError:
    logger.error("Redis server is down.")
    sys.exit(0)

if __name__ == "__main__":

    # get just the checks
    checks = [{'id': 123, 'name': 'mic', 'url': 'https://gist.githubusercontent.com/michaelneale/15619020aa2270c74607/raw/dabd6754a0aa56d633245a94163b0918230afd2f/gistfile1.json'}]

    # flush redis db and write the checks in it
    _REDIS_SERVER.flushdb()
    for check in checks:
        _REDIS_SERVER.rpush("checks", check['id'])
        _REDIS_SERVER.set("check:%s" % check['id'], check['name'])
                
    metrics_monitor.run(check['id'], check['name'], check['url'])    