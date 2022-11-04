from collective.elasticsearch import logger
from collective.elasticsearch.interfaces import IElasticSettings
from plone.registry.interfaces import IRegistry
from plone.uuid.interfaces import IUUID
from Products.ZCatalog import ZCatalog
from Products.ZCatalog.CatalogBrains import AbstractCatalogBrain
from typing import List
from zope.component import getUtility

import math
import os
import pkg_resources


HAS_REDIS_MODULE = False
try:
    pkg_resources.get_distribution("redis")
    HAS_REDIS_MODULE = True
except pkg_resources.DistributionNotFound:
    HAS_REDIS_MODULE = False


PLONE_REDIS_DSN = os.environ.get("PLONE_REDIS_DSN", None)
PLONE_USERNAME = os.environ.get("PLONE_USERNAME", None)
PLONE_PASSWORD = os.environ.get("PLONE_PASSWORD", None)
PLONE_BACKEND = os.environ.get("PLONE_BACKEND", None)


def getUID(obj):
    value = IUUID(obj, None)
    if not value and hasattr(obj, "UID"):
        value = obj.UID()
    return value


def get_brain_from_path(zcatalog: ZCatalog, path: str) -> AbstractCatalogBrain:
    rid = zcatalog.uids.get(path)
    if isinstance(rid, int):
        try:
            return zcatalog[rid]
        except KeyError:
            logger.error(f"Couldn't get catalog entry for path: {path}")
    else:
        logger.error(f"Got a key for path that is not integer: {path}")
    return None


def get_settings():
    """Return IElasticSettings values."""
    registry = getUtility(IRegistry)
    try:
        settings = registry.forInterface(IElasticSettings, check=False)
    except Exception:  # noQA
        settings = None
    return settings


def get_connection_settings():
    settings = get_settings()
    return settings.hosts, {
        "retry_on_timeout": settings.retry_on_timeout,
        "sniff_on_connection_fail": settings.sniff_on_connection_fail,
        "sniff_on_start": settings.sniff_on_start,
        "sniffer_timeout": settings.sniffer_timeout,
        "timeout": settings.timeout,
    }


def getESOnlyIndexes():
    settings = get_settings()
    try:
        indexes = settings.es_only_indexes
        return set(indexes) if indexes else set()
    except (KeyError, AttributeError):
        return {"Title", "Description", "SearchableText"}


def batches(data: list, size: int) -> List[List]:
    """Create a batch of lists from a base list."""
    return [data[i : i + size] for i in range(0, len(data), size)]  # noQA


def format_size_mb(value: int) -> str:
    """Format a size, in bytes, to mb."""
    value = value / 1024.0 / 1024.0
    return f"{int(math.ceil(value))} MB"


def is_redis_available():
    """Determens if redis could be available"""
    env_variables = [
        HAS_REDIS_MODULE,
        os.environ.get("PLONE_REDIS_DSN", None),
        os.environ.get("PLONE_USERNAME", None),
        os.environ.get("PLONE_PASSWORD", None),
        os.environ.get("PLONE_BACKEND", None),
    ]
    return all(env_variables)


def use_redis():
    """
    Determens if redis queueing should be used or not.
    """
    return is_redis_available() and get_settings().use_redis
