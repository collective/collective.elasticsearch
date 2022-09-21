from collective.elasticsearch import interfaces
from collective.elasticsearch import logger
from Products.ZCatalog.CatalogBrains import AbstractCatalogBrain
from Products.ZCatalog.interfaces import ICatalogBrain
from typing import Union
from zope.component import getMultiAdapter
from zope.globalrequest import getRequest
from zope.interface import implementer


@implementer(ICatalogBrain)
class ElasticSearchBrain:
    """A Brain containing only information indexed in ElasticSearch."""

    def __init__(self, record: dict):
        self._record = record

    def has_key(self, key):
        return key in self._record

    def __contains__(self, name):
        return name in self._record

    def __getattr__(self, name):
        if not self.__contains__(name):
            raise AttributeError(
                f"'ElasticSearchBrain' object has no attribute '{name}'"
            )
        return self._record[name]

    def getPath(self):
        """Get the physical path for this record"""
        return self._record["path"]["path"]

    def getURL(self, relative=0):
        """Generate a URL for this record"""
        request = getRequest()
        return request.physicalPathToURL(self.getPath(), relative)

    def getObject(self, REQUEST=None):
        return None

    def getRID(self) -> int:
        """Return the record ID for this object."""
        return -1


def BrainFactory(manager):
    def factory(result: dict) -> Union[AbstractCatalogBrain, ElasticSearchBrain]:
        catalog = manager.catalog._catalog
        path = result.get("fields", {}).get("path.path", None)
        if type(path) in (list, tuple, set) and len(path) > 0:
            path = path[0]
        if path:
            rid = catalog.uids.get(path)
            if isinstance(rid, int):
                try:
                    return catalog[rid]
                except KeyError:
                    logger.error(f"Couldn't get catalog entry for path: {path}")
            else:
                logger.error(f"Got not integer key for path: {path}")
            result = manager.get_record_by_path(path)
            return ElasticSearchBrain(record=result)
        # We should handle cases where there is no path in the ES response
        return None

    return factory


class ElasticResult:
    def __init__(self, manager, query, **query_params):
        assert "sort" not in query_params
        assert "start" not in query_params
        self.manager = manager
        self.bulk_size = manager.bulk_size
        qassembler = getMultiAdapter(
            (getRequest(), manager), interfaces.IQueryAssembler
        )
        dquery, self.sort = qassembler.normalize(query)
        self.query = qassembler(dquery)

        # results are stored in a dictionary, keyed
        # but the start index of the bulk size for the
        # results it holds. This way we can skip around
        # for result data in a result object
        result = manager._search(self.query, sort=self.sort, **query_params)["hits"]
        self.results = {0: result["hits"]}
        self.count = result["total"]["value"]
        self.query_params = query_params

    def __len__(self):
        return self.count

    def __getitem__(self, key):
        """
        Lazy loading es results with negative index support.
        We store the results in buckets of what the bulk size is.
        This is so you can skip around in the indexes without needing
        to load all the data.
        Example(all zero based indexing here remember):
            (525 results with bulk size 50)
            - self[0]: 0 bucket, 0 item
            - self[10]: 0 bucket, 10 item
            - self[50]: 50 bucket: 0 item
            - self[55]: 50 bucket: 5 item
            - self[352]: 350 bucket: 2 item
            - self[-1]: 500 bucket: 24 item
            - self[-2]: 500 bucket: 23 item
            - self[-55]: 450 bucket: 19 item
        """
        bulk_size = self.bulk_size
        count = self.count
        if isinstance(key, slice):
            return [self[i] for i in range(key.start, key.end)]
        if key + 1 > count:
            raise IndexError
        if key < 0 and abs(key) > count:
            raise IndexError
        if key >= 0:
            result_key = int(key / bulk_size) * bulk_size
            start = result_key
            result_index = key % bulk_size
        elif key < 0:
            last_key = int(count / bulk_size) * bulk_size
            last_key = last_key if last_key else count
            start = result_key = int(last_key - ((abs(key) / bulk_size) * bulk_size))
            if last_key == result_key:
                result_index = key
            else:
                result_index = (key % bulk_size) - (bulk_size - (count % last_key))
        if result_key not in self.results:
            self.results[result_key] = self.manager._search(
                self.query, sort=self.sort, start=start, **self.query_params
            )["hits"]["hits"]
        return self.results[result_key][result_index]
