import random
from Acquisition import aq_base
from zope.component import getUtility
from plone.registry.interfaces import IRegistry
from Products.ZCatalog.Lazy import LazyMap
from collective.elasticsearch.brain import BrainFactory
from collective.elasticsearch.query import QueryAssembler
from pyes.exceptions import IndexMissingException
from pyes import ES
from collective.elasticsearch.interfaces import (
    IElasticSettings,
    DISABLE_MODE,
    DUAL_MODE)
from collective.elasticsearch.utils import sid
from plone.indexer.interfaces import IIndexableObject
from zope.component import queryMultiAdapter
from collective.elasticsearch.indexes import getIndex
from Missing import MV
from Products.PluginIndexes.common import safe_callable
from DateTime import DateTime
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from logging import getLogger
import traceback
from collective.elasticsearch.indexes import getPath
from pyes.exceptions import IndexAlreadyExistsException
import transaction
from zope.globalrequest import getRequest


logger = getLogger(__name__)
info = logger.info
warn = logger.warn

CONVERTED_ATTR = '_elasticconverted'
REQ_CONN_ATTR = 'elasticsearch.connection'


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
            self.req = getRequest()
        except:
            self.req = None

        registry = getUtility(IRegistry)
        try:
            self.registry = registry.forInterface(IElasticSettings)
        except:
            self.registry = None

        current = transaction.get()
        hooked = False
        for hook in current.getAfterCommitHooks():
            meth = hook[0]
            if getattr(meth, 'im_class', None) == ElasticSearch:
                self.tid = hook[1][0]
                hooked = True
                break
        if not hooked:
            self.tid = self.generateTransactionId()
            current.addAfterCommitHook(self.afterCommit, (self.tid,))

    def generateTransactionId(self):
        return random.randint(0, 9999999999)

    def afterCommit(self, success, tid):
        # XXX implement
        pass

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
    def conn(self):
        if self.req is not None:
            if REQ_CONN_ATTR not in self.req.environ:
                self.req.environ[REQ_CONN_ATTR] = \
                    ES(self.registry.connection_string)
            return self.req.environ[REQ_CONN_ATTR]
        else:
            return ES(self.registry.connection_string)

    def query(self, query):
        qassembler = QueryAssembler(self.catalogtool)
        dquery, sort = qassembler.normalize(query)
        equery = qassembler(dquery)
        result = self.conn.search(equery, self.catalogsid, self.catalogtype, sort=sort)
        factory = BrainFactory(self.catalog)
        count = result.count()
        result =  LazyMap(factory, result, count)
        return result

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
            wrapper = queryMultiAdapter((obj, self.catalogtool), IIndexableObject)
            if wrapper is not None:
                wrapped_object = wrapper
            else:
                wrapped_object = obj
        else:
            wrapped_object = obj
        conn = self.conn
        catalog = self.catalog
        orig_idxs = idxs
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
            for meta_name in catalog.names:
                if meta_name in index_data:
                    continue
                attr = getattr(wrapped_object, meta_name, MV)
                if (attr is not MV and safe_callable(attr)):
                    attr = attr()
                if isinstance(attr, DateTime):
                    attr = attr.ISO8601()
                elif attr in (MV, 'None'):
                    attr = None
                index_data[meta_name] = attr

        # only if full indexing 
        if orig_idxs == [] and 'path' not in index_data:
            if uid:
                index_data['path'] = uid
            else:
                index_data['path'] = getPath(wrapped_object)

        conn.index(index_data, self.catalogsid, self.catalogtype, sid(obj))
        if self.registry.auto_flush:
            conn.refresh()

    def uncatalog_object(self, obj, *args, **kwargs):
        mode = self.mode
        if mode in (DISABLE_MODE, DUAL_MODE):
            result = self.patched.uncatalog_object(obj, *args, **kwargs)
            if mode == DISABLE_MODE:
                return result
        conn = self.conn
        conn.delete(self.catalogsid, self.catalogtype, sid(obj))
        if self.registry.auto_flush:
            conn.refresh()

    def manage_catalogRebuild(self, REQUEST=None, RESPONSE=None):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.manage_catalogRebuild(REQUEST, RESPONSE)

        self.recreateCatalog()

        return self.patched.manage_catalogRebuild(REQUEST, RESPONSE)

    def manage_catalogClear(self, REQUEST=None, RESPONSE=None, URL1=None):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.manage_catalogClear(REQUEST, RESPONSE, URL1)

        self.recreateIndex()

        if mode == DUAL_MODE:
            return self.patched.manage_catalogClear(REQUEST, RESPONSE, URL1)

    def refreshCatalog(self, clear=0, pghandler=None):
        mode = self.mode
        if mode == DISABLE_MODE:
            return self.patched.refreshCatalog(clear, pghandler)

        return self.patched.refreshCatalog(clear, pghandler)

    def recreateCatalog(self):
        conn = self.conn
        try:
            conn.delete_index(self.catalogsid)
            conn.delete_index(self.trns_catalogtype)
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
            query['allowedRolesAndUsers'] = self.catalogtool._listAllowedRolesAndUsers(user)

            if not show_inactive and not _checkPermission(
                    AccessInactivePortalContent, self.catalogtool):
                query['effectiveRange'] = DateTime()
        orig_query = query.copy()
        # info('Running query: %s' % repr(orig_query))
        try:
            return self.query(query)
        except:
            info("Error running Query: %s\n%s" %(
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
            conn.create_index(self.trns_catalogtype)
        except IndexAlreadyExistsException:
            pass

        mapping = {'properties': properties}
        conn.indices.put_mapping(
            doc_type=self.catalogtype,
            mapping=mapping,
            indices=[self.catalogsid])
        conn.indices.put_mapping(
            doc_type=self.trns_catalogtype,
            mapping=mapping,
            indices=[self.catalogsid])

    @property
    def catalogsid(self):
        return sid(self.catalogtool)

    @property
    def catalogtype(self):
        return self.catalogtool.getId()

    @property
    def trns_catalogtype(self):
        return self.catalogtype + '_trns'
