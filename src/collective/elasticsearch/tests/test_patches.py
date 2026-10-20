from collective.elasticsearch.testing import ElasticSearch_FUNCTIONAL_TESTING
from collective.elasticsearch.testing import ElasticSearch_REDIS_TESTING
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.monkeypatcher.meta import _do_patch
from parameterized import parameterized_class
from plone import api
from zope.configuration import config
from zope.configuration import xmlconfig

import collective.elasticsearch.patches
import transaction
import unittest


@parameterized_class(
    [
        {"layer": ElasticSearch_FUNCTIONAL_TESTING},
        {"layer": ElasticSearch_REDIS_TESTING},
    ]
)
class TestZmiRemoveSyncsElasticsearch(BaseFunctionalTest):
    def setUp(self):
        super().setUp()
        self.event = api.content.create(
            self.portal, "Event", "event-test", title="Gone Event"
        )
        self.commit(wait=1)
        self.path = "/".join(self.event.getPhysicalPath())
        self.query = {"portal_type": "Event", "Title": "Gone Event"}

    def zmi_remove(self):
        self.catalog.manage_uncatalogObject(
            self.request,
            self.request.response,
            self.portal.absolute_url(),
            urls=[self.path],
        )

    def test_removes_the_elasticsearch_document_after_commit(self):
        self.zmi_remove()
        self.commit(wait=1)
        self.assertEqual(
            self.total_results(self.query),
            0,
            "The ZMI remove must delete the elasticsearch document",
        )

    def test_keeps_the_elasticsearch_document_on_abort(self):
        self.zmi_remove()
        transaction.abort()
        self.assertEqual(
            self.total_results(self.query),
            1,
            "An aborted ZMI remove must not delete the elasticsearch document",
        )

    def test_removes_the_elasticsearch_document_of_a_stale_entry(self):
        self.portal._delObject("event-test", suppress_events=True)
        self.commit(wait=1)
        self.assertEqual(
            self.total_results(self.query),
            1,
            "Precondition: the stale catalog entry must still be in elasticsearch",
        )
        self.zmi_remove()
        self.commit(wait=1)
        self.assertEqual(
            self.total_results(self.query),
            0,
            "The ZMI remove of a stale entry must delete the elasticsearch document",
        )


class TestRemainingPatches(unittest.TestCase):
    def registered_patches(self):
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
            if action["callable"] is _do_patch
        }

    def test_only_the_zmi_remove_is_patched(self):
        self.assertEqual(
            self.registered_patches(),
            {"manage_uncatalogObject"},
            "The package must not monkeypatch anything else, in particular "
            "no portal_catalog search method",
        )


class TestDeleteSyncsElasticsearch(BaseFunctionalTest):
    def test_delete_removes_the_elasticsearch_document(self):
        api.content.create(self.portal, "Event", "event-test", title="Gone Event")
        self.commit(wait=1)
        self.portal.manage_delObjects(ids=["event-test"])
        self.commit(wait=1)
        self.assertEqual(
            self.total_results({"portal_type": "Event", "Title": "Gone Event"}),
            0,
            "Deleting content must delete the elasticsearch document",
        )
