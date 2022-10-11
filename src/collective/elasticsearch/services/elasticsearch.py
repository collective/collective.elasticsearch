from collective.elasticsearch.manager import ElasticSearchManager
from plone import api
from plone.restapi.deserializer import json_body
from plone.restapi.services import Service


class ElasticSearchService(Service):
    """Base service for ElasticSearch management."""

    def __init__(self, context, request):
        super().__init__(context, request)
        self.es = ElasticSearchManager()


class Info(ElasticSearchService):
    """Elastic Search information."""

    def reply(self):
        info = self.es.info
        response = dict(info)
        response["@id"] = f"{api.portal.get().absolute_url()}/@elasticsearch"
        return response


class Maintenance(ElasticSearchService):
    """Elastic Search integration management."""

    def reply(self):
        data = json_body(self.request)
        action = data.get("action")
        if action == "convert":
            self.es._convert_catalog_to_elastic()
        elif action == "rebuild":
            catalog = api.portal.get_tool("portal_catalog")
            catalog.manage_catalogRebuild()
        else:
            return self.reply_no_content(status=400)
        return self.reply_no_content()
