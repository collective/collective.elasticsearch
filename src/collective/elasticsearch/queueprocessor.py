from collective.elasticsearch import logger
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.interfaces import IAdditionalIndexDataProvider
from collective.elasticsearch.interfaces import IElasticSearchIndexQueueProcessor
from collective.elasticsearch.interfaces import IndexingActions
from collective.elasticsearch.interfaces import IReindexActive
from collective.elasticsearch.manager import ElasticSearchManager
from collective.elasticsearch.utils import getESOnlyIndexes
from collective.elasticsearch.utils import use_redis
from pkg_resources import parse_version
from plone import api
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.dexterity.utils import iterSchemata
from plone.indexer.interfaces import IIndexableObject
from plone.indexer.interfaces import IIndexer
from plone.namedfile.interfaces import INamedBlobFileField
from zope.component import getAdapters
from zope.component import queryMultiAdapter
from zope.component.hooks import getSite
from zope.globalrequest import getRequest
from zope.interface import implementer
from zope.schema import getFields

import transaction


if parse_version(api.env.plone_version()) < parse_version("6"):

    def uuidToObject(uuid, unrestricted=False):
        """Variation of this method, which support the parameter
        'unrestricted', like the one from plone 6.
        """

        brain = uuidToCatalogBrain(uuid)
        if brain is None:
            return None

        path = brain.getPath()

        if not path:
            return
        site = getSite()
        if site is None:
            return
        # Go to the parent of the item without restrictions.
        parent_path, final_path = path.rpartition("/")[::2]
        parent = site.unrestrictedTraverse(parent_path)
        # Do check restrictions for the final object.
        # Check if the object has restrictions
        if unrestricted:
            return parent.unrestrictedTraverse(final_path)
        return parent.restrictedTraverse(final_path)

else:
    from plone.app.uuid.utils import uuidToObject


@implementer(IElasticSearchIndexQueueProcessor)
class IndexProcessor:
    """A queue processor for elasticsearch"""

    _manager: ElasticSearchManager = None
    _es_attributes = None
    _all_attributes = None
    rebuild: bool = False
    _actions: IndexingActions = None

    @property
    def manager(self):
        """Return the portal catalog."""
        if not self._manager:
            self._manager = ElasticSearchManager()
        return self._manager

    @property
    def catalog(self):
        """Return the portal catalog."""
        return api.portal.get_tool("portal_catalog")

    @property
    def es_attributes(self):
        """Return all attributes defined in portal catalog."""
        if not self._es_attributes:
            self._es_attributes = getESOnlyIndexes()
        return self._es_attributes

    @property
    def all_attributes(self):
        """Return all attributes defined in portal catalog."""
        if not self._all_attributes:
            catalog = self.catalog
            es_indexes = self.es_attributes
            catalog_indexes = set(catalog.indexes())
            self._all_attributes = es_indexes.union(catalog_indexes)
        return self._all_attributes

    @property
    def rebuild(self):
        return IReindexActive.providedBy(getRequest())

    @property
    def actions(self) -> IndexingActions:
        if not self._actions:
            self._actions = IndexingActions(
                index={},
                reindex={},
                unindex={},
                index_blobs={},
                uuid_path={},
            )
        return self._actions

    def _clean_up(self):
        self._manager = None
        self._es_attributes = None
        self._all_attributes = None
        self._actions = None

    def _uuid_path(self, obj):
        uuid = api.content.get_uuid(obj) if obj.portal_type != "Plone Site" else "/"
        path = "/".join(obj.getPhysicalPath())
        return uuid, path

    def index(self, obj, attributes=None):
        """Index the specified attributes for an obj."""
        actions = self.actions
        uuid, path = self._uuid_path(obj)
        actions.uuid_path[uuid] = path
        if self.rebuild:
            # During rebuild we index everything
            attributes = self.all_attributes
            is_reindex = False
        else:
            attributes = {att for att in attributes} if attributes else set()
            is_reindex = attributes and attributes != self.all_attributes
        data = self.get_data(uuid, attributes)
        blob_data = self.get_blob_data(uuid, obj)
        if is_reindex and uuid in actions.index:
            # Reindexing something that was not processed yet
            actions.index[uuid].update(data)
            return
        elif is_reindex:
            # Simple reindexing
            actions.reindex[uuid] = data
            actions.index_blobs[uuid] = blob_data
            return
        elif uuid in actions.reindex:
            # Remove from reindex
            actions.reindex.pop(uuid)

        elif uuid in actions.unindex:
            # Remove from unindex
            actions.unindex.pop(uuid)
        actions.index[uuid] = data
        actions.index_blobs[uuid] = blob_data

    def reindex(self, obj, attributes=None, update_metadata=False):
        """Reindex the specified attributes for an obj."""
        self.index(obj, attributes)

    def unindex(self, obj):
        """Unindex the obj."""
        actions = self.actions
        uuid, path = self._uuid_path(obj)
        actions.uuid_path[uuid] = path
        if uuid in actions.index:
            actions.index.pop(uuid)
        elif uuid in actions.reindex:
            actions.reindex.pop(uuid)
        actions.unindex[uuid] = {}

    def begin(self):
        """Transaction start."""
        pass

    def commit(self, wait=None):
        """Transaction commit."""
        method = self.commit_es
        if use_redis():
            method = self.commit_redis
        return method(wait=wait)

    def commit_redis(self, wait=None):
        """Since we defere indexing to a external queue. We need to make sure
        the transaction is commited and synced with all threads.
        Thus for the redis integration we run the 'commit' in the
        addAfterCommitHook of the transaction
        """

        transaction.get().addAfterCommitHook(self._commit_hook_redis)

    def _commit_hook_redis(self, wait=None):
        """The after commit hook from redis, includes updateing blobs as
        well."""
        actions = self.actions
        items = len(actions) if actions else 0
        if self.manager.active and items:
            self.manager.bulk(data=actions.all())

        # make sure attachment plugin and cbor-attachments pipeline are available
        pipeline = "cbor-attachments" in self.manager.connection.ingest.get_pipeline()
        plugin = "attachment" in self.manager.connection.cat.plugins()
        if pipeline and plugin:
            for item in self.actions.all_blob_actions():
                self.manager.update_blob(item)

        self._clean_up()

    def commit_es(self, wait=None):
        """Transaction commit."""
        actions = self.actions
        items = len(actions) if actions else 0
        if self.manager.active and items:
            self.manager.bulk(data=actions.all())
        self._clean_up()

    def abort(self):
        """Transaction abort."""
        self._clean_up()

    def wrap_object(self, obj):
        wrapped_object = None
        if not IIndexableObject.providedBy(obj):
            # This is the CMF 2.2 compatible approach, which should be used
            # going forward
            wrapper = queryMultiAdapter((obj, self.catalog), IIndexableObject)
            wrapped_object = wrapper if wrapper is not None else obj
        else:
            wrapped_object = obj
        return wrapped_object

    def get_data(self, uuid, attributes=None):
        method = self.get_data_for_es
        if use_redis():
            method = self.get_data_for_redis
        return method(uuid, attributes=attributes)

    def get_data_for_redis(self, uuid, attributes=None):
        attributes = attributes if attributes else self.all_attributes
        index_data = {}
        for index_name in attributes:
            index_data[index_name] = None
        return index_data

    def get_data_for_es(self, uuid, attributes=None):
        """Data to be sent to elasticsearch."""
        obj = api.portal.get() if uuid == "/" else uuidToObject(uuid, unrestricted=True)
        wrapped_object = self.wrap_object(obj)
        index_data = {}
        attributes = attributes if attributes else self.all_attributes
        catalog = self.catalog
        for index_name in attributes:
            value = None
            index = getIndex(catalog, index_name)
            if index is not None:
                try:
                    value = index.get_value(wrapped_object)
                except Exception as exc:  # NOQA W0703
                    path = "/".join(obj.getPhysicalPath())
                    logger.error(f"Error indexing value: {path}: {index_name}\n{exc}")
                    value = None
                if value in (None, "None"):
                    # yes, we'll index null data...
                    value = None
            elif index_name in self._es_attributes:
                indexer = queryMultiAdapter(
                    (wrapped_object, catalog), IIndexer, name=index_name
                )
                if indexer:
                    value = indexer()
                else:
                    attr = getattr(obj, index_name, None)
                    value = attr() if callable(attr) else value
            # Use str, if bytes value
            value = (
                value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
            )
            index_data[index_name] = value
        additional_providers = [
            adapter for adapter in getAdapters((obj,), IAdditionalIndexDataProvider)
        ]
        if additional_providers:
            for _, adapter in additional_providers:
                index_data.update(adapter(catalog, index_data))

        return index_data

    def get_blob_data(self, uuid, obj):
        """Go thru schemata and extract infos about blob fields"""
        index_data = {}
        portal_path_len = len(api.portal.get().getPhysicalPath())
        obj_segements = obj.getPhysicalPath()
        relative_path = "/".join(obj_segements[portal_path_len:])
        for schema in iterSchemata(obj):
            for name, field in getFields(schema).items():
                if INamedBlobFileField.providedBy(field) and field.get(obj):
                    index_data[name] = {
                        "path": relative_path,
                        "filename": field.get(obj).filename,
                    }
        return index_data
