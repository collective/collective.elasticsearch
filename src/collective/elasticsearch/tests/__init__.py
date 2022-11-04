from collective.elasticsearch import utils
from collective.elasticsearch.browser.controlpanel import ElasticControlPanelView
from collective.elasticsearch.interfaces import IElasticSearchIndexQueueProcessor
from collective.elasticsearch.manager import ElasticSearchManager
from collective.elasticsearch.testing import ElasticSearch_API_TESTING
from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING
from collective.elasticsearch.testing import ElasticSearch_INTEGRATION_TESTING
from collective.elasticsearch.testing import ElasticSearch_REDIS_TESTING
from plone import api
from Products.CMFCore.indexing import processQueue
from zope.component import getUtility

import time
import transaction
import unittest


MAX_CONNECTION_RETRIES = 20


class BaseTest(unittest.TestCase):
    layer = ElasticSearch_INTEGRATION_TESTING

    def get_processor(self):
        return getUtility(IElasticSearchIndexQueueProcessor, name="elasticsearch")

    def setUp(self):
        super().setUp()
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        self.request.environ["testing"] = True
        self.app = self.layer["app"]

        settings = utils.get_settings()
        # disable sniffing hosts in tests because docker...
        settings.sniffer_timeout = None
        settings.enabled = True
        settings.sniffer_timeout = 0.0

        self._wait_for_es_service()

        self.catalog = api.portal.get_tool("portal_catalog")
        self.catalog._elasticcustomindex = "plone-test-index"
        self.es = ElasticSearchManager()

        self.catalog.manage_catalogRebuild()
        # need to commit here so all tests start with a baseline
        # of elastic enabled
        time.sleep(0.1)
        self.commit()

    def commit(self, wait: int = 0):
        processQueue()
        transaction.commit()
        self.es.flush_indices()
        if wait:
            time.sleep(wait)

    def tearDown(self):
        super().tearDown()
        real_index_name = f"{self.es.real_index_name}_1"
        index_name = self.es.index_name
        conn = self.es.connection
        conn.indices.delete_alias(index=real_index_name, name=index_name)
        conn.indices.delete(index=real_index_name)
        conn.indices.flush()
        # Wait ES remove the index
        time.sleep(0.1)

    def _wait_for_es_service(self):
        controlpanel = ElasticControlPanelView(self.portal, self.request)
        counter = 0
        while not controlpanel.connection_status:
            if counter == MAX_CONNECTION_RETRIES:
                raise Exception("Cannot connect to elasticsearch service")
            time.sleep(1)
            counter += 1


class BaseFunctionalTest(BaseTest):
    layer = ElasticSearch_FUNCTIONAL_TESTING

    def search(self, query: dict):
        return self.catalog(**query)

    def total_results(self, query: dict):
        results = self.search(query)
        return len(results)


class BaseAPITest(BaseTest):

    layer = ElasticSearch_API_TESTING


class BaseRedisTest(BaseTest):

    layer = ElasticSearch_REDIS_TESTING
