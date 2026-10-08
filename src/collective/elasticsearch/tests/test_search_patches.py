from collective.elasticsearch import local
from collective.elasticsearch.testing import DISABLE_SEARCH_PATCHES
from collective.elasticsearch.testing import ElasticSearch_NO_SEARCH_PATCHES_TESTING
from collective.elasticsearch.testing import SEARCH_PATCHED_METHODS
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import get_settings
from collective.monkeypatcher.meta import _do_patch
from contextlib import contextmanager
from plone import api
from plone.app.testing import logout
from Products.CMFPlone.CatalogTool import CatalogTool
from zope.configuration import config
from zope.configuration import xmlconfig

import collective.elasticsearch.patches
import os
import unittest


MAINTENANCE_METHODS = {
    "manage_catalogRebuild",
    "manage_catalogClear",
    "uncatalog_object",
}


class TestSearchPatchRouting(BaseFunctionalTest):
    def test_es_only_index_in_query_dict_is_searched_in_elasticsearch(self):
        api.content.create(self.portal, "Document", "fancy", title="A Fancy Title")
        api.content.create(self.portal, "Document", "other", title="Other Page")
        self.commit(wait=1)
        self.delete_es_only_indexes_from_catalog()
        results = self.catalog({"portal_type": "Document", "SearchableText": "fancy"})
        self.assertEqual(
            [brain.getId for brain in results],
            ["fancy"],
            "SearchableText passed in the query dict must be searched in elasticsearch",
        )


class TestSearchPatchFallback(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        get_settings().raise_search_exception = False
        self.create_private_page()

    @contextmanager
    def unreachable_elasticsearch(self):
        settings = get_settings()
        hosts = settings.hosts
        settings.hosts = ["127.0.0.1:1"]
        local.set_local(self.es.connection_key, None)
        try:
            yield
        finally:
            settings.hosts = hosts
            local.set_local(self.es.connection_key, None)

    def test_unrestricted_search_falls_back_to_unrestricted_catalog_search(self):
        logout()
        with self.unreachable_elasticsearch():
            results = self.catalog.unrestrictedSearchResults(SearchableText="secret")
        self.assertEqual(
            [brain.getId for brain in results],
            ["page"],
            "The fallback of an unrestricted search must not be restricted",
        )

    def test_restricted_search_falls_back_to_restricted_catalog_search(self):
        logout()
        with self.unreachable_elasticsearch():
            results = self.catalog(SearchableText="secret")
        self.assertEqual(
            len(results), 0, "The fallback of a restricted search must stay restricted"
        )


class TestSearchPatchSwitch(unittest.TestCase):
    def setUp(self):
        self.env_value = os.environ.pop(DISABLE_SEARCH_PATCHES, None)

    def tearDown(self):
        os.environ.pop(DISABLE_SEARCH_PATCHES, None)
        if self.env_value is not None:
            os.environ[DISABLE_SEARCH_PATCHES] = self.env_value

    def patched_catalog_methods(self):
        context = config.ConfigurationMachine()
        xmlconfig.registerCommonDirectives(context)
        xmlconfig.file(
            "configure.zcml",
            collective.elasticsearch.patches,
            context=context,
            execute=False,
        )
        return {
            action["args"][2]
            for action in context.actions
            if action["callable"] is _do_patch and action["args"][1] is CatalogTool
        }

    def test_search_patches_are_loaded_by_default(self):
        self.assertEqual(
            self.patched_catalog_methods(),
            set(SEARCH_PATCHED_METHODS) | MAINTENANCE_METHODS,
            "Without the environment variable the search must be patched",
        )

    def test_environment_variable_disables_only_the_search_patches(self):
        os.environ[DISABLE_SEARCH_PATCHES] = "1"
        self.assertEqual(
            self.patched_catalog_methods(),
            MAINTENANCE_METHODS,
            "The environment variable must only disable the search patches",
        )


class TestWithoutSearchPatches(BaseFunctionalTest):
    layer = ElasticSearch_NO_SEARCH_PATCHES_TESTING

    def test_catalog_search_is_not_patched(self):
        for name in SEARCH_PATCHED_METHODS:
            self.assertNotEqual(
                getattr(CatalogTool, name).__module__,
                "collective.elasticsearch.patches",
                f"CatalogTool.{name} must not be patched",
            )
            self.assertNotIn(
                f"_old_{name}",
                CatalogTool.__dict__,
                f"CatalogTool.{name} must not keep a patched original",
            )

    def test_maintenance_patches_are_applied(self):
        for name in MAINTENANCE_METHODS:
            self.assertEqual(
                getattr(CatalogTool, name).__module__,
                "collective.elasticsearch.patches",
                f"CatalogTool.{name} must be patched to keep elasticsearch in sync",
            )

    def test_catalog_searches_the_catalog_only(self):
        api.content.create(self.portal, "Document", "page", title="A Fancy Title")
        self.commit(wait=1)
        self.delete_es_only_indexes_from_catalog()
        results = self.catalog(portal_type="Document", SearchableText="nothing")
        self.assertEqual(
            [brain.getId for brain in results],
            ["page"],
            "The catalog ignores the removed SearchableText index",
        )
