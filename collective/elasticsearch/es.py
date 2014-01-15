from logging import getLogger
import traceback

from Acquisition import aq_base
from DateTime import DateTime
from Products.ZCatalog.Lazy import LazyMap
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from zope.component import getUtility
from zope.component import queryMultiAdapter
from zope.component import ComponentLookupError

from plone.registry.interfaces import IRegistry
from plone.indexer.interfaces import IIndexableObject

from pyes import ES
from pyes.exceptions import (
    IndexAlreadyExistsException,
    NotFoundException,
    IndexMissingException
)
from pyes.es import (
    ResultSet as BaseResultSet,
    ElasticSearchModel as BaseElasticSearchModel,
    DotDict
)

from collective.elasticsearch.brain import BrainFactory
from collective.elasticsearch.query import QueryAssembler
from collective.elasticsearch.interfaces import (
    IElasticSettings, DISABLE_MODE, DUAL_MODE)
from collective.elasticsearch.utils import getUID
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch import td


logger = getLogger(__name__)
info = logger.info
warn = logger.warn

CONVERTED_ATTR = '_elasticconverted'


class ElasticSearchModel(BaseElasticSearchModel):
    """
    overriding this because the original pops values off
    the original item dict which screws up additional calls
    to the model constructor
    """
    def __init__(self, *args, **kwargs):
        self._meta = DotDict()
        self.__initialised = True
        if len(args) == 2 and isinstance(args[0], ES):
            item = args[1]
            self.update(item.get("_source", DotDict()))
            self.update(item.get("fields", {}))
            self._meta = DotDict([(k.lstrip("_"), v) for k, v in item.items()])
            self._meta.parent = self.pop("_parent", None)
            self._meta.connection = args[0]
        else:
            self.update(dict(*args, **kwargs))


class ResultSet(BaseResultSet):
    """
    override because the original sucks and does a call for every
    result object. Yikes
    """
    def __init__(self, connection, query, indices=None, doc_types=None,
                 query_params=None, auto_fix_keys=False,
                 auto_clean_highlight=False, model=ElasticSearchModel):
        """
        override...
        """
        self.connection = connection
        self.indices = indices
        self.doc_types = doc_types
        self.query_params = query_params or {}
        self.scroller_parameters = {}
        self.scroller_id = None
        self._results = None
        self.model = model or self.connection.model
        self._total = None
        self.valid = False
        self._facets = {}
        self.auto_fix_keys = auto_fix_keys
        self.auto_clean_highlight = auto_clean_highlight

        from pyes.query import Search

        if not isinstance(query, Search):
            self.query = Search(query)
        else:
            self.query = query

        self.iterpos = 0  # keep track of iterator position
        self.start = self.query.start or query_params.get("start", 0)
        self._max_item = self.query.size
        self._current_item = 0
        self.chuck_size = 400

    def __getitem__(self, val):
        if not isinstance(val, (int, long, slice)):
            raise TypeError('%s indices must be integers, not %s' % (
                self.__class__.__name__, val.__class__.__name__))

        def get_start_end(val):
            if isinstance(val, slice):
                start = val.start
                if not start:
                    start = 0
                end = val.stop or self.total
                if end < 0:
                    end = self.total + end
                if self._max_item is not None and end > self._max_item:
                    end = self._max_item
                return start, end
            return val, val + 1

        start, end = get_start_end(val)
        model = self.model

        if self._results:
            if start >= 0 and end < self.start + self.chuck_size and \
                    len(self._results['hits']['hits']) > 0:
                if not isinstance(val, slice):
                    return model(
                        self.connection,
                        self._results['hits']['hits'][val - self.start])
                else:
                    return [model(self.connection, hit)
                            for hit in
                            self._results['hits']['hits'][start:end]]

        query = self.query.serialize()
        query['from'] = start+self.start
        query['size'] = end - start

        results = self.connection.search_raw(query, indices=self.indices,
                                             doc_types=self.doc_types,
                                             **self.query_params)
        hits = results['hits']['hits']
        if not isinstance(val, slice):
            if len(hits) == 1:
                return model(self.connection, hits[0])
            raise IndexError
        return [model(self.connection, hit) for hit in hits]


class PatchCaller(object):
    """
    Very odd I have to do this. If I don't,
    I get very pecular errors trying to call
    the original methods
    """

    def __init__(self, patched_object):
        self._patched_object = patched_object

    def __getattr__(self, name):
        """
        assuming original attribute has "__old_" prefix
        """
        if name[0] == '_':
            return self.__dict__[name]
        _type = type(aq_base(self._patched_object))
        func = getattr(_type, '__old_' + name)

        # "bind" it
        def bound_func(*args, **kwargs):
            return func(self._patched_object, *args, **kwargs)
        return bound_func


class ElasticSearch(object):

    def __init__(self, catalogtool):
        self.catalogtool = catalogtool
        self.catalog = catalogtool._catalog
        self.patched = PatchCaller(self.catalogtool)

        try:
            registry = getUtility(IRegistry)
            try:
                self.registry = registry.forInterface(IElasticSettings)
            except:
                self.registry = None
        except ComponentLookupError:
            self.registry = None

        self.tdata = td.get()

    @property
    def catalog_converted(self):
        return getattr(self.catalogtool, CONVERTED_ATTR, False)

    @property
    def mode(self):
        if not self.catalog_converted:
            return DISABLE_MODE
        if self.registry is None:
            return DISABLE_MODE
        return self.registry.mode

    @property
    def bulk_size(self):
        try:
            return self.registry.bulk_size
        except:
            return 400

    @property
    def max_retries(self):
        try:
            return self.registry.max_retries
        except:
            return 3

    @property
    def timeout(self):
        try:
            return self.registry.timeout
        except:
            return 30.0

    @property
    def conn(self):
        if self.tdata.conn is None:
            self.tdata.conn = ES(
                self.registry.connection_string,
                bulk_size=self.bulk_size,
                max_retries=self.max_retries,
                timeout=self.timeout,
                model=ElasticSearchModel)
        return self.tdata.conn

    def _es_search(self, query, **query_params):
        """
        override default es search to use our own ResultSet class that works
        """
        indices = self.conn._validate_indices(self.catalogsid)
        if hasattr(query, 'search'):
            query = query.search()

        #propage the start and size in the query object
        from pyes.query import Search
        if "start" in query_params:
            start = query_params.pop("start")
            if isinstance(query, dict):
                query["from"] = start
            elif isinstance(query, Search):
                query.start = start
        if "size" in query_params:
            size = query_params.pop("size")
            if isinstance(query, dict):
                query["size"] = size
            elif isinstance(query, Search):
                query.size = size

        return ResultSet(connection=self.conn, query=query, indices=indices,
                         doc_types=self.catalogtype, query_params=query_params,
                         model=self.conn.model)

    def query(self, query):
        qassembler = QueryAssembler(self.catalogtool)
        dquery, sort = qassembler.normalize(query)
        equery = qassembler(dquery)
        result = self._es_search(equery, sort=sort, fields="path")
        count = result.count()
        # disable this for now. some issues...
        #result = ResultWrapper(result, count=count)
        factory = BrainFactory(self.catalog)
        return LazyMap(factory, result, count)

    def catalog_object(self, obj, uid=None, idxs=[],
                       update_metadata=1, pghandler=None):
        mode = self.mode
        if mode in (DISABLE_MODE, DUAL_MODE):
            result = self.patched.catalog_object(
                obj, uid, idxs, update_metadata, pghandler)
            if mode == DISABLE_MODE:
                return result
        wrapped_object = None
        if not IIndexableObject.providedBy(obj):
            # This is the CMF 2.2 compatible approach, which should be used
            # going forward
            wrapper = queryMultiAdapter((obj, self.catalogtool),
                                        IIndexableObject)
            if wrapper is not None:
                wrapped_object = wrapper
            else:
                wrapped_object = obj
        else:
            wrapped_object = obj
        conn = self.conn
        catalog = self.catalog
        if idxs == []:
            idxs = catalog.indexes.keys()
        index_data = {}
        for index_name in idxs:
            index = getIndex(catalog, index_name)
            if index is not None:
                value = index.get_value(wrapped_object)
                if value in (None, 'None'):
                    # yes, we'll index null data...
                    value = None
                index_data[index_name] = value
        if update_metadata:
            index = self.catalog.uids.get(uid, None)
            if index is None:  # we are inserting new data
                index = self.catalog.updateMetadata(obj, uid, None)
                self.catalog._length.change(1)
                self.catalog.uids[uid] = index
                self.catalog.paths[index] = uid
            # need to match elasticsearch result with brain
            self.catalog.updateMetadata(wrapped_object, uid, index)

        uid = getUID(obj)
        try:
            doc = conn.get(self.catalogsid, self.catalogtype, uid)
            self.registerInTransaction(uid, td.Actions.modify, doc)
        except NotFoundException:
            self.registerInTransaction(uid, td.Actions.add)
        conn.index(index_data, self.catalogsid, self.catalogtype, uid)
        if self.registry.auto_flush:
            conn.refresh()

    def registerInTransaction(self, uid, action, doc={}):
        if not self.tdata.registered:
            self.tdata.register(self)
        self.tdata.docs.append(
            (action, uid, doc)
        )

    def uncatalog_object(self, uid, obj=None, *args, **kwargs):
        mode = self.mode
        if mode in (DISABLE_MODE, DUAL_MODE):
            if self.catalog.uids.get(uid, None) is not None:
                result = self.patched.uncatalog_object(uid, *args, **kwargs)
            if mode == DISABLE_MODE:
                return result
        conn = self.conn

        uid = getUID(obj)
        try:
            doc = conn.get(self.catalogsid, self.catalogtype, uid)
            self.registerInTransaction(uid, td.Actions.delete, doc)
        except NotFoundException:
            pass
        try:
            conn.delete(self.catalogsid, self.catalogtype, uid)
        except NotFoundException:
            # already gone... Multiple calls?
            pass
        if self.registry.auto_flush:
            conn.refresh()

    def manage_catalogRebuild(self, *args, **kwargs):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.manage_catalogRebuild(*args, **kwargs)

        self.recreateCatalog()

        return self.patched.manage_catalogRebuild(*args, **kwargs)

    def manage_catalogClear(self, *args, **kwargs):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.manage_catalogClear(*args, **kwargs)

        self.recreateCatalog()

        if mode == DUAL_MODE:
            return self.patched.manage_catalogClear(*args, **kwargs)

    def refreshCatalog(self, clear=0, pghandler=None):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.refreshCatalog(clear, pghandler)

        return self.patched.refreshCatalog(clear, pghandler)

    def recreateCatalog(self):
        conn = self.conn
        try:
            conn.delete_index(self.catalogsid)
        except IndexMissingException:
            pass
        self.convertToElastic()

    def searchResults(self, REQUEST=None, check_perms=False, **kw):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.searchResults(REQUEST, **kw)
        if isinstance(REQUEST, dict):
            query = REQUEST.copy()
        else:
            query = {}
        query.update(kw)

        if check_perms:
            show_inactive = query.get('show_inactive', False)
            if isinstance(REQUEST, dict) and not show_inactive:
                show_inactive = 'show_inactive' in REQUEST

            user = _getAuthenticatedUser(self.catalogtool)
            query['allowedRolesAndUsers'] = \
                self.catalogtool._listAllowedRolesAndUsers(user)

            if not show_inactive and not _checkPermission(
                    AccessInactivePortalContent, self.catalogtool):
                query['effectiveRange'] = DateTime()
        orig_query = query.copy()
        # info('Running query: %s' % repr(orig_query))
        try:
            return self.query(query)
        except:
            info("Error running Query: %s\n%s" % (
                repr(orig_query),
                traceback.format_exc()))
            if mode == DUAL_MODE:
                # fall back now...
                return self.patched.searchResults(REQUEST, **kw)
            else:
                return LazyMap(BrainFactory(self.catalog), [], 0)

    def convertToElastic(self):
        setattr(self.catalogtool, CONVERTED_ATTR, True)
        self.catalogtool._p_changed = True
        properties = {}
        for name in self.catalog.indexes.keys():
            index = getIndex(self.catalog, name)
            if index is not None:
                properties[name] = index.create_mapping(name)
            else:
                raise Exception("Can not locate index for %s" % (
                    name))

        conn = self.conn
        try:
            conn.create_index(self.catalogsid)
        except IndexAlreadyExistsException:
            pass

        mapping = {'properties': properties}
        conn.indices.put_mapping(
            doc_type=self.catalogtype,
            mapping=mapping,
            indices=[self.catalogsid])

    @property
    def catalogsid(self):
        return '-'.join(self.catalogtool.getPhysicalPath()[1:]).lower()

    @property
    def catalogtype(self):
        return self.catalogtool.getId().lower()
