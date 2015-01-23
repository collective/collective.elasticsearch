from Acquisition import aq_parent
from AccessControl import Unauthorized
from Products.Five import BrowserView
from zope.component import getMultiAdapter

from collective.elasticsearch.es import ElasticSearchCatalog


class Utils(BrowserView):

    def convert(self):
        if self.request.method == 'POST':
            authenticator = getMultiAdapter((self.context, self.request),
                                            name=u'authenticator')
            if not authenticator.verify():
                raise Unauthorized

            es = ElasticSearchCatalog(self.context)
            es.convertToElastic()
        site = aq_parent(self.context)
        self.request.response.redirect('%s/@@elastic-controlpanel' % (
            site.absolute_url()))

    def rebuild(self):
        if self.request.method == 'POST':
            authenticator = getMultiAdapter((self.context, self.request),
                                            name=u'authenticator')
            if not authenticator.verify():
                raise Unauthorized

            self.context.manage_catalogRebuild()

        site = aq_parent(self.context)
        self.request.response.redirect('%s/@@elastic-controlpanel' % (
            site.absolute_url()))
