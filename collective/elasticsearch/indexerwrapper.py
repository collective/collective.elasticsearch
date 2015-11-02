from Products.ZCatalog.interfaces import IZCatalog
from collective.elasticsearch import hook
from collective.elasticsearch.utils import getUID
from plone.indexer.wrapper import IndexableObjectWrapper
from zope.component import adapts
from plone.dexterity.interfaces import IDexterityItem
from Products.PluginIndexes.common import safe_callable


class CachedIndexableObjectWrapper(IndexableObjectWrapper):
    """
    XXX NOT ENABLED. WILL NOT WORK
    cache results here so we can improve performance and not run
    indexes twice
    """

    adapts(IDexterityItem, IZCatalog)

    def __getattr__(self, name):
        val = super(CachedIndexableObjectWrapper, self).__getattr__(name)
        if safe_callable(val):
            val = val()
        _hook = hook.getHook()
        if _hook:
            uid = getUID(self._getWrappedObject())
            # do not want to cache too much
            if uid not in _hook.cached_index_data:
                if len(_hook.cached_index_data) < 50:
                    _hook.cached_index_data[uid] = {}
                    _hook.cached_index_data[uid][name] = val
            else:
                _hook.cached_index_data[uid][name] = val
        return val