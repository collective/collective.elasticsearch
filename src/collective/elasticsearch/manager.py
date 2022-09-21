from collective.elasticsearch import interfaces
from collective.elasticsearch import local
from collective.elasticsearch import logger
from collective.elasticsearch import utils
from collective.elasticsearch.result import BrainFactory
from collective.elasticsearch.result import ElasticResult
from DateTime import DateTime
from elasticsearch import Elasticsearch
from elasticsearch import exceptions
from plone import api
from Products.CMFCore.indexing import processQueue
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFPlone.CatalogTool import CatalogTool
from zope.component import getMultiAdapter
from zope.globalrequest import getRequest
from zope.interface import implementer
from ZTUtils.Lazy import LazyMap

import warnings


CONVERTED_ATTR = "_elasticconverted"
CUSTOM_INDEX_NAME_ATTR = "_elasticcustomindex"
INDEX_VERSION_ATTR = "_elasticindexversion"


@implementer(interfaces.IElasticSearchManager)
class ElasticSearchManager:

    _catalog: CatalogTool = None
    connection_key = "elasticsearch_connection"

    def __init__(self):
        settings = utils.get_settings()
        self.bulk_size = settings.bulk_size

    @property
    def catalog(self):
        return api.portal.get_tool("portal_catalog")

    @property
    def catalog_converted(self):
        return getattr(self.catalog, CONVERTED_ATTR, False)

    @property
    def enabled(self):
        settings = utils.get_settings()
        return settings.enabled

    @property
    def active(self):
        return self.enabled and self.catalog_converted

    @property
    def index_version(self):
        return getattr(self.catalog, INDEX_VERSION_ATTR, None)

    @property
    def index_name(self):
        catalog = self.catalog
        name = getattr(catalog, CUSTOM_INDEX_NAME_ATTR, None)
        if not name:
            name = "-".join(catalog.getPhysicalPath()[1:]).lower()
        return name

    @property
    def real_index_name(self):
        if self.index_version and not hasattr(self.catalog, CUSTOM_INDEX_NAME_ATTR):
            return f"{self.index_name}_{self.index_version}"
        return self.index_name

    def bump_index_version(self):
        version = getattr(self.catalog, INDEX_VERSION_ATTR, None)
        version = version + 1 if version else 1
        setattr(self.catalog, INDEX_VERSION_ATTR, version)
        self.catalog._p_changed = True
        return version

    def _recreate_catalog(self):
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
        self.flush_indices()
        self._convert_catalog_to_elastic()

    def _convert_catalog_to_elastic(self):
        setattr(self.catalog, CONVERTED_ATTR, True)
        self.catalog._p_changed = True
        mapping = getMultiAdapter((getRequest(), self), interfaces.IMappingProvider)()
        self.connection.indices.put_mapping(body=mapping, index=self.index_name)

    @property
    def connection(self) -> Elasticsearch:
        conn = local.get_local(self.connection_key)
        if not conn:
            hosts, params = utils.get_connection_settings()
            local.set_local(self.connection_key, Elasticsearch(hosts, **params))
            conn = local.get_local(self.connection_key)
        return conn

    def _bulk_call(self, batch):
        data = [item for sublist in batch for item in sublist]
        logger.info(f"Bulk call with {len(data)} entries and {len(batch)} actions.")
        result = self.connection.bulk(index=self.index_name, body=data)
        if "errors" in result and result["errors"] is True:
            logger.error(f"Error in bulk operation: {result}")

    def flush_indices(self):
        self.connection.indices.flush()

    def bulk(self, data: list):
        index_name = self.index_name
        bulk_data = []
        for action, uuid, payload in data:
            tmp = [
                {action: {"_index": index_name, "_id": uuid}},
            ]
            if action == "index":
                tmp.append(payload)
            elif action == "update":
                tmp.append({"doc": payload})
            bulk_data.append(tmp)
        calls = 0
        for batch in utils.batches(bulk_data, self.bulk_size):
            self._bulk_call(batch)
            calls += 1

    def _search(self, query, sort=None, **query_params):
        """ """
        if "start" in query_params:
            query_params["from_"] = query_params.pop("start")

        query_params["stored_fields"] = query_params.get("stored_fields", "path.path")
        query_params["size"] = self.bulk_size

        body = {"query": query}
        if sort is not None:
            body["sort"] = sort
        warnings.simplefilter("ignore", ResourceWarning)
        return self.connection.search(index=self.index_name, body=body, **query_params)

    def search(self, query: dict, factory=None, **query_params) -> LazyMap:
        """
        @param query: The Plone query
        @param factory: The factory that maps each elastic search result.
            By default, get the plone catalog brain.
        @param query_params: Parameters to pass to the search method
            'stored_fields': the list of fields to get from stored source
        """
        factory = BrainFactory(self.catalog._catalog)
        result = ElasticResult(self, query, **query_params)
        return LazyMap(factory, result, result.count)

    def search_results(self, request=None, check_perms=False, **kw):
        # Make sure any pending index tasks have been processed
        processQueue()
        if not (self.active and utils.getESOnlyIndexes().intersection(kw.keys())):
            method = (
                self.catalog._old_searchResults
                if check_perms
                else self.catalog._old_unrestrictedSearchResults
            )
            return method(request, **kw)

        query = request.copy() if isinstance(request, dict) else {}
        query.update(kw)

        if check_perms:
            show_inactive = query.get("show_inactive", False)
            if isinstance(request, dict) and not show_inactive:
                show_inactive = "show_inactive" in request

            user = api.user.get_current()
            query["allowedRolesAndUsers"] = self.catalog._listAllowedRolesAndUsers(user)

            if not show_inactive and not _checkPermission(
                AccessInactivePortalContent, self.catalog
            ):
                query["effectiveRange"] = DateTime()
        orig_query = query.copy()
        logger.debug(f"Running query: {orig_query}")
        try:
            return self.search(query)
        except Exception:  # NOQA W0703
            logger.error(f"Error running Query: {orig_query}", exc_info=True)
            return self.catalog._old_searchResults(request, **kw)
