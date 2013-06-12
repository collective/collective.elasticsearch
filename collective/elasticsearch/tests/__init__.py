# coding: utf-8
from zope.component import getUtility
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from collective.elasticsearch.testing import \
    ElasticSearch_INTEGRATION_TESTING, \
    ElasticSearch_FUNCTIONAL_TESTING
import unittest2 as unittest
from collective.elasticsearch.es import ElasticSearch, PatchCaller
from collective.elasticsearch.interfaces import (
    IElasticSettings,
    DUAL_MODE)
import transaction
from collective.elasticsearch import td


class BaseTest(unittest.TestCase):

    layer = ElasticSearch_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.app = self.layer['app']

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IElasticSettings)
        settings.mode = DUAL_MODE

        self.catalog = getToolByName(self.portal, 'portal_catalog')
        self.es = ElasticSearch(self.catalog)
        self.es.convertToElastic()
        self.catalog.manage_catalogRebuild()
        # need to commit here so all tests start with a baseline
        # of elastic enabled
        transaction.commit()
        patched = PatchCaller(self.catalog)
        self.searchResults = patched.searchResults
        td.transactionJoiner(None)

    def clearTransactionEntries(self):
        tdata = td.get()
        tdata.reset(True)

    def tearDown(self):
        self.es.conn.delete_index(self.es.catalogsid)
        self.clearTransactionEntries()


class BaseFunctionalTest(BaseTest):

    layer = ElasticSearch_FUNCTIONAL_TESTING
