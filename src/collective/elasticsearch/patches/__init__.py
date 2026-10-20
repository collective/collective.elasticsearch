from collective.elasticsearch.manager import ElasticSearchManager
from collective.elasticsearch.utils import get_brain_from_path

import transaction


def delete_from_elasticsearch(status, data):
    if status:
        ElasticSearchManager().bulk(data=data)


def manage_uncatalogObject(self, REQUEST, RESPONSE, URL1, urls=None):
    """Remove the entries from the catalog and from elasticsearch."""
    manager = ElasticSearchManager()
    if manager.active and urls:
        urls = (urls,) if isinstance(urls, str) else urls
        brains = [get_brain_from_path(self._catalog, path) for path in urls]
        data = [("delete", brain.UID, {}) for brain in brains if brain]
        if data:
            transaction.get().addAfterCommitHook(delete_from_elasticsearch, (data,))
    return self._old_manage_uncatalogObject(REQUEST, RESPONSE, URL1, urls=urls)
