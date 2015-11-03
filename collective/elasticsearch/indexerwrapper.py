from Products.ZCatalog.interfaces import IZCatalog
from collective.elasticsearch import hook
from collective.elasticsearch.utils import getUID
from plone.indexer.wrapper import IndexableObjectWrapper
from zope.component import adapts
from plone.dexterity.interfaces import IDexterityItem
from Products.PluginIndexes.common import safe_callable


class CachedIndexableObjectWrapper(IndexableObjectWrapper):
    """
    cache results here so we can improve performance and not run
    indexes twice
    """

    adapts(IDexterityItem, IZCatalog)

    def __getattr__(self, name):
        orig_value = super(CachedIndexableObjectWrapper, self).__getattr__(name)

        def val():
            if safe_callable(orig_value):
                value = orig_value()
            else:
                value = orig_value

            if type(value) in (str, unicode, bool, int, None):
                _hook = hook.getHook()
                if _hook:
                    uid = getUID(self._getWrappedObject())
                    # do not want to cache too much
                    if uid not in _hook.cached_index_data:
                        if len(_hook.cached_index_data) < 50:
                            _hook.cached_index_data[uid] = {}
                            _hook.cached_index_data[uid][name] = value
                    else:
                        _hook.cached_index_data[uid][name] = value
            return value
        return val