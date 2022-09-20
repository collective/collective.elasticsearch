from collective.elasticsearch.interfaces import IElasticSettings
from plone.registry.interfaces import IRegistry
from plone.uuid.interfaces import IUUID
from typing import List
from zope.component import getUtility


def getUID(obj):
    value = IUUID(obj, None)
    if not value and hasattr(obj, "UID"):
        value = obj.UID()
    return value


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
