from zope.interface import implements
from collective.elasticsearch.indexes import getIndex
from elasticsearch.exceptions import ElasticsearchException
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
        try:
            conn.indices.create(self.es.index_name)
        except ElasticsearchException:
            pass

        return {'properties': properties}