from collective.elasticsearch import hook
from collective.elasticsearch.es import ElasticSearchCatalog
from collective.elasticsearch.interfaces import IElasticSettings
from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING
from collective.elasticsearch.testing import ElasticSearch_INTEGRATION_TESTING
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility

import time
import transaction
import unittest2 as unittest


class BaseTest(unittest.TestCase):

    layer = ElasticSearch_INTEGRATION_TESTING

    def setUp(self):
        super().setUp()
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        self.request.environ["testing"] = True
        self.app = self.layer["app"]

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IElasticSettings, check=False)
        # disable sniffing hosts in tests because docker...
        settings.sniffer_timeout = None
        settings.enabled = True
        settings.sniffer_timeout = 0.0

        self.catalog = getToolByName(self.portal, "portal_catalog")
        self.catalog._elasticcustomindex = "plone-test-index"
        self.es = ElasticSearchCatalog(self.catalog)
        self.catalog.manage_catalogRebuild()
        # need to commit here so all tests start with a baseline
        # of elastic enabled
        self.commit()

    def commit(self):
        transaction.commit()

    def clearTransactionEntries(self):
        _hook = hook.getHook(self.es)
        _hook.remove = []
        _hook.index = {}

    def tearDown(self):
        super().tearDown()
        self.es.connection.indices.delete_alias(
            index=self.es.real_index_name, name=self.es.index_name
        )
        self.es.connection.indices.delete(index=self.es.real_index_name)
        self.clearTransactionEntries()
        # Wait ES remove the index
        time.sleep(0.1)


class BaseFunctionalTest(BaseTest):

    layer = ElasticSearch_FUNCTIONAL_TESTING
