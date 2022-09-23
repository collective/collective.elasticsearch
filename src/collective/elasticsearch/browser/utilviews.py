from AccessControl import Unauthorized
from Acquisition import aq_parent
from collective.elasticsearch.manager import ElasticSearchManager
from Products.Five import BrowserView
from zope.component import getMultiAdapter


class Utils(BrowserView):
    def convert(self):
        if self.request.method == "POST":
            authenticator = getMultiAdapter(
                (self.context, self.request), name="authenticator"
            )
            if not authenticator.verify():
                raise Unauthorized

            es = ElasticSearchManager()
            es._convert_catalog_to_elastic()
        site = aq_parent(self.context)
        self.request.response.redirect(f"{site.absolute_url()}/@@elastic-controlpanel")

    def rebuild(self):
        if self.request.method == "POST":
            authenticator = getMultiAdapter(
                (self.context, self.request), name="authenticator"
            )
            if not authenticator.verify():
                raise Unauthorized

            self.context.manage_catalogRebuild()

        site = aq_parent(self.context)
        self.request.response.redirect(f"{site.absolute_url()}/@@elastic-controlpanel")
