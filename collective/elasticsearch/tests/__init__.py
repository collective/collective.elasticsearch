# coding: utf-8
from zope.component import getUtility
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from collective.elasticsearch.testing import \
    ElasticSearch_INTEGRATION_TESTING, \
    ElasticSearch_FUNCTIONAL_TESTING
import unittest2 as unittest
from pyes import ES
from collective.elasticsearch.es import ElasticSearch, PatchCaller
from collective.elasticsearch.convert import convert_to_elastic
from collective.elasticsearch.utils import sid
from collective.elasticsearch.interfaces import (
    IElasticSettings,
    DUAL_MODE)


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
        self.convert_catalog()
        patched = PatchCaller(self.catalog)
        self.searchResults = patched.searchResults

    def tearDown(self):
        conn = ES('127.0.0.1:9200')
        conn.delete_index(sid(self.catalog))

    def convert_catalog(self):
        convert_to_elastic(self.catalog)


class BaseFunctionalTest(BaseTest):

    layer = ElasticSearch_FUNCTIONAL_TESTING
