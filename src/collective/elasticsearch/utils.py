from collective.elasticsearch import logger
from collective.elasticsearch.interfaces import IElasticSettings
from plone.registry.interfaces import IRegistry
from plone.uuid.interfaces import IUUID
from Products.ZCatalog import ZCatalog
from Products.ZCatalog.CatalogBrains import AbstractCatalogBrain
from typing import List
from zope.component import getUtility

import importlib.metadata
import math
import os


HAS_REDIS_MODULE = False
try:
    importlib.metadata.distribution("redis")
    HAS_REDIS_MODULE = True
except importlib.metadata.PackageNotFoundError:
    HAS_REDIS_MODULE = False


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
    try:
        registry = getUtility(IRegistry)
        settings = registry.forInterface(IElasticSettings, check=False)
    except Exception:  # noQA
        settings = None
    return settings


def normalize_hosts(hosts: List[str]) -> List[str]:
    """Add the scheme and the default port the client requires to the hosts."""
    normalized = []
    for host in hosts:
        if host.startswith(("http://", "https://")):
            normalized.append(host)
        elif ":" in host:
            normalized.append(f"http://{host}")
        else:
            normalized.append(f"http://{host}:9200")
    return normalized


def get_connection_params(settings) -> dict:
    """Build the Elasticsearch client parameters from IElasticSettings."""
    params = {
        "retry_on_timeout": settings.retry_on_timeout,
        "request_timeout": settings.timeout,
    }
    # Only enable sniffing if explicitly configured, it can cause connection
    # issues in Docker/test environments
    if settings.sniff_on_start:
        params["sniff_on_start"] = True
    if settings.sniff_on_connection_fail:
        params["sniff_on_node_failure"] = True
    if settings.sniffer_timeout and settings.sniffer_timeout > 0:
        params["min_delay_between_sniffing"] = settings.sniffer_timeout
    return params


def get_connection_settings():
    settings = get_settings()
    return normalize_hosts(settings.hosts), get_connection_params(settings)


def has_attachment_processor(conn) -> bool:
    """Whether a node of the cluster provides the ingest attachment processor."""
    try:
        nodes_info = conn.nodes.info(metric="ingest")
    except Exception:  # noQA
        return False
    return any(
        processor.get("type") == "attachment"
        for node in nodes_info.get("nodes", {}).values()
        for processor in node.get("ingest", {}).get("processors", [])
    )


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
    env_variables_required = [
        HAS_REDIS_MODULE,
        os.environ.get("PLONE_REDIS_DSN", None),
        os.environ.get("PLONE_USERNAME", None),
        os.environ.get("PLONE_PASSWORD", None),
    ]
    env_any_required = [
        os.environ.get("PLONE_BACKEND", None),
        os.environ.get("PLONE_BACKEND_HOST", None),
    ]
    return all(env_variables_required) and any(env_any_required)


def use_redis():
    """
    Determens if redis queueing should be used or not.
    """
    return is_redis_available() and get_settings().use_redis
