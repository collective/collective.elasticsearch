from collective.elasticsearch import interfaces
from collective.elasticsearch import local
from collective.elasticsearch import logger
from collective.elasticsearch import utils
from collective.elasticsearch.result import BrainFactory
from collective.elasticsearch.result import ElasticResult
from collective.elasticsearch.utils import use_redis
from DateTime import DateTime
from elasticsearch import Elasticsearch
from elasticsearch import exceptions
from elasticsearch.exceptions import NotFoundError
from plone import api
from Products.CMFCore.indexing import processQueue
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFPlone.CatalogTool import CatalogTool
from zope.component import getMultiAdapter
from zope.globalrequest import getRequest
from zope.interface import implementer
from ZTUtils.Lazy import LazyMap

import os
import warnings


CONVERTED_ATTR = "_elasticconverted"
CUSTOM_INDEX_NAME_ATTR = "_elasticcustomindex"
INDEX_VERSION_ATTR = "_elasticindexversion"


@implementer(interfaces.IElasticSearchManager)
class ElasticSearchManager:

    _catalog: CatalogTool = None
    connection_key = "elasticsearch_connection"

    @property
    def raise_search_exception(self):
        """Whether to raise search exceptions or fallback to old catalog search"""
        try:
            value = api.portal.get_registry_record(
                "raise_search_exception", interfaces.IElasticSettings, False
            )
        except KeyError:
            value = False
        return value

    @property
    def bulk_size(self) -> int:
        """Bulk size of ElasticSearch calls."""
        try:
            value = api.portal.get_registry_record(
                "bulk_size", interfaces.IElasticSettings, 50
            )
        except KeyError:
            value = 50
        return value

    @property
    def highlight(self):
        """Is search highlighting enabled in the control panel."""
        try:
            value = api.portal.get_registry_record(
                "highlight", interfaces.IElasticSettings, False
            )
        except KeyError:
            value = False
        return value

    @property
    def highlight_threshold(self):
        """Search highlighting threshold."""
        try:
            value = api.portal.get_registry_record(
                "highlight_threshold", interfaces.IElasticSettings, False
            )
        except KeyError:
            value = 600
        return value

    @property
    def highlight_pre_tags(self):
        """Search highlighting pre tags."""
        try:
            value = api.portal.get_registry_record(
                "highlight_pre_tags", interfaces.IElasticSettings, ""
            )
        except KeyError:
            value = ""
        if value is None:
            value = ""
        return value

    @property
    def highlight_post_tags(self):
        """Search highlighting post tags."""
        try:
            value = api.portal.get_registry_record(
                "highlight_post_tags", interfaces.IElasticSettings, ""
            )
        except KeyError:
            value = ""
        if value is None:
            value = ""
        return value

    @property
    def catalog(self):
        return api.portal.get_tool("portal_catalog")

    @property
    def catalog_converted(self):
        return getattr(self.catalog, CONVERTED_ATTR, False)

    @property
    def enabled(self):
        try:
            value = api.portal.get_registry_record(
                "enabled", interfaces.IElasticSettings, False
            )
        except KeyError:
            value = False
        return value

    @property
    def info(self) -> list:
        """Return Information about ElasticSearch."""
        conn = self.connection
        index_name = self.real_index_name
        catalog = api.portal.get_tool("portal_catalog")
        zcatalog = catalog._catalog
        catalog_docs = len(zcatalog.getIndex("UID"))
        try:
            info = conn.info()
            cluster_name = info.get("name")
            cluster_version = info.get("version", {}).get("number")
            try:
                index_stats = conn.indices.stats(index=index_name)["indices"]
                if index_name not in index_stats:
                    index_name = f"{index_name}_{self.index_version}"
                stats = index_stats[index_name]["primaries"]
                size_in_mb = utils.format_size_mb(stats["store"]["size_in_bytes"])
                return [
                    ("Cluster Name", cluster_name),
                    ("Index Name", index_name),
                    ("Elastic Search Version", cluster_version),
                    ("Number of docs (Catalog)", catalog_docs),
                    ("Number of docs", stats["docs"]["count"]),
                    ("Deleted docs", stats["docs"]["deleted"]),
                    ("Size", size_in_mb),
                    ("Query Count", stats["search"]["query_total"]),
                ]
            except KeyError:
                return [
                    ("Cluster Name", cluster_name),
                    ("Elastic Search Version", cluster_version),
                    ("Number of docs (Catalog)", catalog_docs),
                ]
        except NotFoundError:
            logger.warning("Error getting stats", exc_info=True)
            return []

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

    def _bump_index_version(self):
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
        self._setup_attachment_pipeline_and_default_index()

    def _setup_attachment_pipeline_and_default_index(self):
        """
        Setup the cbor-attachments pipeline:
        1. Iterate over all attachments (field) and use the attachment processor
           to extract text data from the binary/data field called 'data'.
        2. Iterate over all extracted data and extend the SearchableText.
           At same time remove the binary data to save some space. With
           Version 8 of elasticsearch we could use the remove_binary flag, but
           it does not exist yet in version 7.
        It's called cbor-attachment pipeline, because the data is transfered
        using cbor. This eliminates the base64 overhead.

        Also the cbor-attachments pipline is used as default pipeline for the index.
        There is a condition defined, so the pipeline is only triggered if
        actual binary data is available to extract.
        """

        if "attachment" not in self.connection.cat.plugins():
            return

        body = {
            "description": "Extract attachment information and append extracted data to SearchableText",
            "processors": [
                {
                    "foreach": {
                        "if": 'ctx.containsKey("attachments")',
                        "field": "attachments",
                        "processor": {
                            "attachment": {
                                "target_field": "_ingest._value.attachment",
                                "field": "_ingest._value.data",
                                # "remove_binary": "true",  # version 8
                                "properties": ["content"],
                            }
                        },
                    }
                },
                {
                    "script": {
                        "if": 'ctx.containsKey("attachments")',
                        "source": """
                            for(int i=0; i<ctx['attachments'].length;++i) {
                                if(ctx['attachments'][i]['attachment'].containsKey('content')) {
                                    if (ctx['attachments'][i]['attachment']['content'].length() > 0) {
                                        ctx['SearchableText'] += ctx['attachments'][i]['attachment']['content'];
                                    }
                                    ctx['attachments'][i]['data'] = null;
                                }
                            }
                            """,
                    }
                },
            ],
            # Enable this for debugging the pipeline
            # "on_failure": [
            #     {
            #         "set": {
            #             "description": "Record error information",
            #             "field": "error_information",
            #             "value": "Processor {{ _ingest.on_failure_processor_type }} with tag {{ _ingest.on_failure_processor_tag }} in pipeline {{ _ingest.on_failure_pipeline }} failed with message {{ _ingest.on_failure_message }}"
            #         }
            #     }
            # ]
        }
        self.connection.ingest.put_pipeline("cbor-attachments", body=body)

        settings = {"index": {"default_pipeline": "cbor-attachments"}}
        self.connection.indices.put_settings(body=settings, index=self.index_name)

    @property
    def connection(self) -> Elasticsearch:
        conn = local.get_local(self.connection_key)
        if not conn:
            hosts, params = utils.get_connection_settings()
            local.set_local(self.connection_key, Elasticsearch(hosts, **params))
            conn = local.get_local(self.connection_key)
        return conn

    def _bulk_call(self, batch):
        method = self._bulk_call_direct
        if use_redis():
            method = self._bulk_call_redis
        return method(batch)

    def _bulk_call_direct(self, batch):
        data = [item for sublist in batch for item in sublist]
        logger.info(f"Bulk call with {len(data)} entries and {len(batch)} actions.")
        result = self.connection.bulk(index=self.index_name, body=data)
        if "errors" in result and result["errors"] is True:
            logger.error(f"Error in bulk operation: {result}")

    def _bulk_call_redis(self, batch):
        from collective.elasticsearch.redis.tasks import bulk_update

        logger.info(f"Bulk call with {len(batch)} entries and {len(batch)} actions.")
        hosts, params = utils.get_connection_settings()

        bulk_update.delay(
            hosts,
            params,
            index_name=self.index_name,
            body=batch,
            plone_url=self.get_plone_url(),
        )
        logger.info("redis task created")

    def update_blob(self, item):
        from collective.elasticsearch.redis.tasks import update_file_data

        hosts, params = utils.get_connection_settings()

        if item[1]:
            update_file_data.delay(
                hosts,
                params,
                index_name=self.index_name,
                body=item,
                plone_url=self.get_plone_url(),
            )
            logger.info("redis task to index blob data created")

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

    def get_record_by_path(self, path: str) -> dict:
        body = {"query": {"match": {"path.path": path}}}
        results = self.connection.search(index=self.index_name, body=body)
        hits = results.get("hits", {}).get("hits", [])
        record = hits[0]["_source"] if hits else {}
        return record

    def get_plone_url(self):
        """This enables multiple plone sites in one ZODB/storage"""
        plone_url = None
        backend_host = os.environ.get("PLONE_BACKEND_HOST", None)
        if backend_host:
            plone_url = backend_host + "/".join(api.portal.get().getPhysicalPath())
        return plone_url

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
        if self.highlight:
            body["highlight"] = {
                "fields": {"SearchableText": {"number_of_fragments": 5}},
                "pre_tags": self.highlight_pre_tags.split("\n"),
                "post_tags": self.highlight_post_tags.split("\n"),
            }
        return self.connection.search(index=self.index_name, body=body, **query_params)

    def search(self, query: dict, factory=None, **query_params) -> LazyMap:
        """
        @param query: The Plone query
        @param factory: The factory that maps each elastic search result.
            By default, get the plone catalog brain.
        @param query_params: Parameters to pass to the search method
            'stored_fields': the list of fields to get from stored source
        """
        factory = BrainFactory(self)
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
            if self.raise_search_exception is True:
                raise
            logger.error(f"Error running Query: {orig_query}", exc_info=True)
            return self.catalog._old_searchResults(request, **kw)
