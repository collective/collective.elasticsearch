from collective.elasticsearch import hook
from collective.elasticsearch import interfaces
from collective.elasticsearch import logger
from collective.elasticsearch import utils
from collective.elasticsearch.brain import BrainFactory
from DateTime import DateTime
from elasticsearch import Elasticsearch
from elasticsearch import exceptions
from plone import api
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import _getAuthenticatedUser
from zope.component import getMultiAdapter
from zope.globalrequest import getRequest
from zope.interface import alsoProvides
from zope.interface import implementer
from ZTUtils.Lazy import LazyMap

import warnings


CONVERTED_ATTR = "_elasticconverted"
CUSTOM_INDEX_NAME_ATTR = "_elasticcustomindex"
INDEX_VERSION_ATTR = "_elasticindexversion"


class ElasticResult:
    def __init__(self, es, query, **query_params):
        assert "sort" not in query_params
        assert "start" not in query_params
        self.es = es
        self.bulk_size = es.get_setting("bulk_size", 50)
        qassembler = getMultiAdapter((getRequest(), es), interfaces.IQueryAssembler)
        dquery, self.sort = qassembler.normalize(query)
        self.query = qassembler(dquery)

        # results are stored in a dictionary, keyed
        # but the start index of the bulk size for the
        # results it holds. This way we can skip around
        # for result data in a result object
        result = es._search(self.query, sort=self.sort, **query_params)["hits"]
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
            self.results[result_key] = self.es._search(
                self.query, sort=self.sort, start=start, **self.query_params
            )["hits"]["hits"]
        return self.results[result_key][result_index]


@implementer(interfaces.IElasticSearchCatalog)
class ElasticSearchCatalog:
    """
    from patched methods
    """

    def __init__(self, catalogtool):
        self.catalogtool = catalogtool
        self.catalog = catalogtool._catalog
        self.registry = utils.get_settings()
        self._conn = None

    @property
    def connection(self):
        if self._conn is None:
            kwargs = {}
            if self.get_setting("timeout", 0):
                kwargs["timeout"] = self.get_setting("timeout")
            if self.get_setting("sniff_on_start", False):
                kwargs["sniff_on_start"] = True
            if self.get_setting("sniff_on_connection", False):
                kwargs["sniff_on_connection"] = True
            if self.get_setting("sniffer_timeout", 0):
                kwargs["sniffer_timeout"] = self.get_setting("sniffer_timeout")
            if self.get_setting("retry_on_timeout", False):
                kwargs["retry_on_timeout"] = True
            self._conn = Elasticsearch(self.registry.hosts, **kwargs)
        return self._conn

    def _search(self, query, sort=None, **query_params):
        """ """
        if "start" in query_params:
            query_params["from_"] = query_params.pop("start")

        query_params["stored_fields"] = query_params.get("stored_fields", "path.path")
        query_params["size"] = self.get_setting("bulk_size", 50)

        body = {"query": query}
        if sort is not None:
            body["sort"] = sort
        warnings.simplefilter("ignore", ResourceWarning)
        return self.connection.search(index=self.index_name, body=body, **query_params)

    def search(self, query, factory=None, **query_params):
        """
        @param query: dict
            The plone query
        @param factory: function(result: dict): any
            The factory that maps each elastic search result.
            By default, get the plone catalog brain.
        @param query_params:
            Parameters to pass to the search method
            'stored_fields': the list of fields to get from stored source
        @return: LazyMap
        """
        result = ElasticResult(self, query, **query_params)
        if not factory:
            factory = BrainFactory(self.catalog)
        return LazyMap(factory, result, result.count)

    @property
    def catalog_converted(self):
        return getattr(self.catalogtool, CONVERTED_ATTR, False)

    @property
    def enabled(self):
        return self.registry and self.registry.enabled and self.catalog_converted

    def get_setting(self, name, default=None):
        return getattr(self.registry, name, default)

    def catalog_object(
        self,
        obj,
        uid=None,
        idxs=None,
        update_metadata=1,
        # NOQA R0913
        pghandler=None,
    ):
        if idxs is None:
            idxs = []
        if idxs != ["getObjPositionInParent"]:
            self.catalogtool._old_catalog_object(
                obj, uid, idxs, update_metadata, pghandler
            )
        if not self.enabled:
            return
        hook.add_object(self, obj)

    def uncatalog_object(self, uid, obj=None, *args, **kwargs):  # NOQA W1113
        # always need to uncatalog to remove brains, etc
        if obj is None:
            # with archetypes, the obj is not passed, only the uid is
            try:
                obj = api.content.get(uid)
            except KeyError:
                pass

        result = self.catalogtool._old_uncatalog_object(uid, *args, **kwargs)
        if self.enabled:
            hook.remove_object(self, obj)

        return result

    def manage_catalogRebuild(self, *args, **kwargs):
        if self.registry.enabled:
            self.recreateCatalog()

        alsoProvides(getRequest(), interfaces.IReindexActive)
        return self.catalogtool._old_manage_catalogRebuild(*args, **kwargs)

    def manage_catalogClear(self, *args, **kwargs):
        if self.enabled:
            self.recreateCatalog()

        return self.catalogtool._old_manage_catalogClear(*args, **kwargs)

    def recreateCatalog(self):
        conn = self.connection

        try:
            conn.indices.delete(index=self.real_index_name)
        except exceptions.NotFoundError:
            pass
        except exceptions.TransportError as exc:
            if exc.error != "illegal_argument_exception":
                raise
            conn.indices.delete_alias(index="_all", name=self.real_index_name)

        if self.index_version:
            try:
                conn.indices.delete_alias(self.index_name, self.real_index_name)
            except exceptions.NotFoundError:
                pass
        self.convertToElastic()

    def searchResults(self, REQUEST=None, check_perms=False, **kw):
        enabled = False
        if self.enabled:
            # need to also check if it is a search result we care about
            # using EL for
            if utils.getESOnlyIndexes().intersection(kw.keys()):
                enabled = True
        if not enabled:
            if check_perms:
                return self.catalogtool._old_searchResults(REQUEST, **kw)
            return self.catalogtool._old_unrestrictedSearchResults(REQUEST, **kw)

        if isinstance(REQUEST, dict):
            query = REQUEST.copy()
        else:
            query = {}
        query.update(kw)

        if check_perms:
            show_inactive = query.get("show_inactive", False)
            if isinstance(REQUEST, dict) and not show_inactive:
                show_inactive = "show_inactive" in REQUEST

            user = _getAuthenticatedUser(self.catalogtool)
            query["allowedRolesAndUsers"] = self.catalogtool._listAllowedRolesAndUsers(
                user
            )

            if not show_inactive and not _checkPermission(
                AccessInactivePortalContent, self.catalogtool
            ):
                query["effectiveRange"] = DateTime()
        orig_query = query.copy()
        logger.debug(f"Running query: {orig_query}")
        try:
            results = self.search(query)
            return results
        except Exception:  # NOQA W0703
            logger.error(f"Error running Query: {orig_query}", exc_info=True)
            return self.catalogtool._old_searchResults(REQUEST, **kw)

    def convertToElastic(self):
        setattr(self.catalogtool, CONVERTED_ATTR, True)
        self.catalogtool._p_changed = True
        adapter = getMultiAdapter((getRequest(), self), interfaces.IMappingProvider)
        mapping = adapter()
        self.connection.indices.put_mapping(body=mapping, index=self.index_name)

    @property
    def index_name(self):
        if hasattr(self.catalogtool, CUSTOM_INDEX_NAME_ATTR):
            return getattr(self.catalogtool, CUSTOM_INDEX_NAME_ATTR)
        return "-".join(self.catalogtool.getPhysicalPath()[1:]).lower()

    @property
    def index_version(self):
        return getattr(self.catalogtool, INDEX_VERSION_ATTR, None)

    def bump_index_version(self):
        version = getattr(self.catalogtool, INDEX_VERSION_ATTR, None)
        if version is None:
            version = 1
        else:
            version += 1
        setattr(self.catalogtool, INDEX_VERSION_ATTR, version)
        self.catalogtool._p_changed = True
        return version

    @property
    def real_index_name(self):
        if self.index_version and not hasattr(self.catalogtool, CUSTOM_INDEX_NAME_ATTR):
            return f"{self.index_name}_{self.index_version}"
        return self.index_name
