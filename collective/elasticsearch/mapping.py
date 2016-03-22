from zope.interface import implements
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.interfaces import IMappingProvider


class MappingAdapter(object):
    implements(IMappingProvider)

    _default_mapping = {
        'SearchableText': {'store': False, 'type': 'string', 'index': 'analyzed'},
        'Title': {'store': False, 'type': 'string', 'index': 'analyzed'},
        'Description': {'store': False, 'type': 'string', 'index': 'analyzed'}
    }

    def __init__(self, request, es):
        self.request = request
        self.es = es
        self.catalog = es.catalog

    def __call__(self):
        properties = self._default_mapping.copy()
        for name in self.catalog.indexes.keys():
            index = getIndex(self.catalog, name)
            if index is not None:
                properties[name] = index.create_mapping(name)
            else:
                raise Exception('Can not locate index for %s' % (
                    name))

        conn = self.es.connection
        index_name = self.es.index_name
        if conn.indices.exists(index_name):
            # created BEFORE we started creating this as aliases to versions,
            # we can't go anywhere from here beside try updating...
            pass
        else:
            if not self.es.index_version:
                # need to initialize version value
                self.es.bump_index_version()
            index_name_v = '%s_%i' % (index_name, self.es.index_version)
            if not conn.indices.exists(index_name_v):
                conn.indices.create(index_name_v)
            if not conn.indices.exists_alias(name=index_name):
                conn.indices.put_alias(index=index_name_v, name=index_name)

        return {'properties': properties}
