from collective.elasticsearch import hook
from Products.CMFCore.interfaces import IIndexQueueProcessor
from zope.interface import implementer


@implementer(IIndexQueueProcessor)
class ESCatalogProcessor:
    """An index queue processor for the standard portal catalog via
       the `CatalogMultiplex` and `CMFCatalogAware` mixin classes """

    def index(self, obj, attributes=None):
        print('hi')
        hook.add_object(None, obj)

    def reindex(self, obj, attributes=None, update_metadata=1):
        hook.add_object(None, obj)

    def unindex(self, obj):
        hook.remove_object(None, obj)

    def begin(self):
        pass

    def commit(self):
        pass

    def abort(self):
        pass
