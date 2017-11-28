# -*- coding: utf-8 -*-
# coding: utf-8
from collective.elasticsearch import hook
from collective.elasticsearch.es import ElasticSearchCatalog
from collective.elasticsearch.interfaces import IElasticSettings
from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING
from collective.elasticsearch.testing import ElasticSearch_INTEGRATION_TESTING
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility

import transaction
import unittest2 as unittest


class BaseTest(unittest.TestCase):

    layer = ElasticSearch_INTEGRATION_TESTING

    def setUp(self):
        super(BaseTest, self).setUp()
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.request.environ['testing'] = True
        self.app = self.layer['app']

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IElasticSettings, check=False)
        settings.enabled = True

        self.catalog = getToolByName(self.portal, 'portal_catalog')
        self.catalog._elasticcustomindex = 'plone-test-index'
        self.es = ElasticSearchCatalog(self.catalog)
        self.es.convertToElastic()
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
        super(BaseTest, self).tearDown()
        self.es.connection.indices.delete(index=self.es.index_name)
        self.clearTransactionEntries()


class BaseFunctionalTest(BaseTest):

    layer = ElasticSearch_FUNCTIONAL_TESTING
