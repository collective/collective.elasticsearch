from collective.elasticsearch.interfaces import IElasticSearchIndexQueueProcessor
from plone import api
from plone.restapi.serializer.converters import json_compatible
from plone.restapi.services import Service
from zExceptions import NotFound
from zope.component import getUtility


class ExtractData(Service):
    def reply(self):
        queueprocessor = getUtility(
            IElasticSearchIndexQueueProcessor, name="elasticsearch"
        )
        attributes = self.request.get("attributes", [])
        uuid = self.request.get("uuid", None)

        obj = api.portal.get() if uuid == "/" else api.content.get(UID=uuid)
        if obj is None:
            raise NotFound()

        response = {}
        data = queueprocessor.get_data_for_es(uuid, attributes=attributes)
        response["@id"] = f"{self.context.absolute_url()}/@elasticsearch_extractdata"
        response["data"] = json_compatible(data)
        return response
