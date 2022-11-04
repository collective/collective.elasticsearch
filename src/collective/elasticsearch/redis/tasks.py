from .fetch import fetch_data
from elasticsearch import Elasticsearch
from rq import Queue
from rq import Retry
from rq.decorators import job

import os
import redis


redis_connection = redis.Redis.from_url(os.environ.get("PLONE_REDIS_DSN", None))
queue = Queue(
    "normal",
    connection=redis_connection,
    is_async=os.environ.get("ZOPETESTCASE", "0") == "0",
)  # Don't queue in tests


@job(queue, retry=Retry(max=3, interval=30))
def bulk_update(hosts, params, index_name, body):
    """
    Collects all the data and updates elasticsearch
    """
    connection = Elasticsearch(hosts, **params)

    for item in body:
        if len(item) == 1 and "delete" in item[0]:
            continue

        catalog_info, payload = item
        action, index_info = list(catalog_info.items())[0]
        if action == "index":
            data = fetch_data(uuid=index_info["_id"], attributes=list(payload.keys()))
            item[1] = data
        elif action == "update":
            data = fetch_data(
                uuid=index_info["_id"], attributes=list(payload["doc"].keys())
            )
            item[1]["doc"] = data

    es_data = [item for sublist in body for item in sublist]
    connection.bulk(index=index_name, body=es_data)
    return "Done"
