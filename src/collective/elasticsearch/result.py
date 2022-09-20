from collective.elasticsearch import interfaces
from collective.elasticsearch import logger
from zope.component import getMultiAdapter
from zope.globalrequest import getRequest


def BrainFactory(catalog):
    def factory(result):
        path = result.get("fields", {}).get("path.path", None)
        if type(path) in (list, tuple, set) and len(path) > 0:
            path = path[0]
        if path:
            rid = catalog.uids.get(path)
            try:
                return catalog[rid]
            except TypeError:
                logger.error(f"Got not integer key for result: {result}")
                return None
            except KeyError:
                logger.error(f"Couldn't get catalog entry for result: {result}")
                return None
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
