from zope.component import getMultiAdapter
from AccessControl import Unauthorized
from Products.Five import BrowserView
from collective.elasticsearch.es import ElasticSearch, CONVERTED_ATTR


class ConvertToElastic(BrowserView):

    def __call__(self):
        if self.request.method == 'POST':
            authenticator = getMultiAdapter((self.context, self.request),
                                            name=u"authenticator")
            if not authenticator.verify():
                raise Unauthorized

            setattr(self.context, CONVERTED_ATTR, True)
            self.context._p_changed = True
            self.context.manage_catalogRebuild()
            
        return super(ConvertToElastic, self).__call__()
