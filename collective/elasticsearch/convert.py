from zope.component import getMultiAdapter
from AccessControl import Unauthorized
from Products.Five import BrowserView
from collective.elasticsearch.es import CONVERTED_ATTR
from collective.elasticsearch.indexes import getIndex
from pyes.exceptions import IndexAlreadyExistsException
from collective.elasticsearch.utils import sid
from collective.elasticsearch.es import ElasticSearch


def convert_to_elastic(catalogtool):
    es = ElasticSearch(catalogtool)
    catalog = catalogtool._catalog
    properties = {}
    for name in catalog.indexes.keys():
        index = getIndex(catalog, name)
        if index is not None:
            properties[name] = index.create_mapping(name)
        else:
            raise Exception("Can not locate index for %s" % (
                name))

    conn = es.conn
    try:
        conn.create_index(sid(catalogtool))
    except IndexAlreadyExistsException:
        pass

    mapping = {'properties': properties}
    conn.put_mapping(catalogtool.getId(), mapping,
        [sid(catalogtool)])
    setattr(catalogtool, CONVERTED_ATTR, True)
    catalogtool._p_changed = True
    conn.refresh()


class ConvertToElastic(BrowserView):

    def __call__(self):
        if self.request.method == 'POST':
            authenticator = getMultiAdapter((self.context, self.request),
                                            name=u"authenticator")
            if not authenticator.verify():
                raise Unauthorized

            convert_to_elastic(self.context)
            
        return super(ConvertToElastic, self).__call__()
