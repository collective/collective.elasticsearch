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


logger = getLogger(__name__)
info = logger.info

CONVERTED_ATTR = '_elasticconverted'


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

        registry = getUtility(IRegistry)
        try:
            self.registry = registry.forInterface(IElasticSettings)
        except:
            self.registry = None

    @property
    def mode(self):
        if not getattr(self.catalogtool, CONVERTED_ATTR, False):
            return DISABLE_MODE
        if self.registry is None:
            return DISABLE_MODE
        return self.registry.mode

    @property
    def conn(self):
        return ES(self.registry.connection_string)

    def query(self, query):
        qassembler = QueryAssembler(self.catalogtool)
        try:
            dquery, sort = qassembler.normalize(query)
            equery = qassembler(dquery)
            result = self.conn.search(equery, sid(self.catalogtool), self.catalogtool.getId(),
                                 sort=sort)
            factory = BrainFactory(self.catalog)
            count = result.count()
            result =  LazyMap(factory, result, count)
            return result
        except IndexMissingException:
            """will happen on no result"""
            return LazyMap(BrainFactory(self.catalog), [], 0)

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
        conn = self.conn
        catalog = self.catalog
        if not idxs:
            idxs = catalog.indexes.keys()
        index_data = {}
        for index_name in idxs:
            index = getIndex(catalog, index_name)
            if index is not None:
                value = index.get_value(wrapped_object)
                if value not in (None, 'None'):
                    index_data[index_name] = value
        # now get metadata
        for meta_name in catalog.names:
            if meta_name in index_data:
                continue
            attr = getattr(wrapped_object, meta_name, MV)
            if (attr is not MV and safe_callable(attr)):
                attr = attr()
            if isinstance(attr, DateTime):
                attr = attr.ISO8601()
            elif attr in (MV, 'None'):
                continue
            index_data[meta_name] = attr

        conn.index(index_data, sid(self.catalogtool), self.catalogtool.getId(), sid(obj))
        if self.registry.auto_flush:
            conn.refresh()

    def uncatalog_object(self, obj, *args, **kwargs):
        mode = self.mode
        if mode in (DISABLE_MODE, DUAL_MODE):
            result = self.patched.uncatalog_object(obj, *args, **kwargs)
            if mode == DISABLE_MODE:
                return result
        conn = self.conn
        conn.delete(sid(self.catalogtool), self.catalogtool.getId(), sid(obj))
        if self.registry.auto_flush:
            conn.refresh()

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

        try:
            return self.query(query)
        except:
            info("Error running Query: %s\n%s" %(
                repr(query),
                traceback.format_exc()))
            return LazyMap(BrainFactory(self._catalog), [], 0)