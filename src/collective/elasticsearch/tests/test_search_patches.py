from collective.elasticsearch import local
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.utils import get_settings
from collective.elasticsearch.utils import getESOnlyIndexes
from contextlib import contextmanager
from plone import api
from plone.app.testing import logout


class TestSearchPatchRouting(BaseFunctionalTest):
    def test_es_only_index_in_query_dict_is_searched_in_elasticsearch(self):
        api.content.create(self.portal, "Document", "fancy", title="A Fancy Title")
        api.content.create(self.portal, "Document", "other", title="Other Page")
        self.commit(wait=1)
        for idx in getESOnlyIndexes():
            self.catalog._catalog.delIndex(idx)
        self.commit()
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
        page = api.content.create(self.portal, "Document", "page", title="Secret Page")
        api.content.transition(obj=page, to_state="private")
        self.commit(wait=1)

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
