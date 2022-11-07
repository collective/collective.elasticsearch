from collective.elasticsearch import utils
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.tests import BaseRedisTest
from plone import api
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.textfield import RichTextValue
from plone.restapi.testing import RelativeSession
from unittest import mock

import json
import os
import transaction


ENV_FOR_REDIS = {
    "PLONE_REDIS_DSN": "redis://localhost:6379/0",
    "PLONE_BACKEND": "http://localhost",
    "PLONE_USERNAME": "admin",
    "PLONE_PASSWORD": "password",
}


class TestRedisUtils(BaseFunctionalTest):
    def test_redis_not_available_if_environ_vars_are_missing(self):

        self.assertFalse(
            utils.is_redis_available(), "Env vars are missing, this should be false"
        )

        with mock.patch.dict(os.environ, ENV_FOR_REDIS):
            self.assertTrue(
                True,
                "All env vars ar available, this should be true",
            )


class TestUseRedis(BaseRedisTest):
    def test_use_redis_if_configured(self):
        utils.get_settings().use_redis = False
        self.assertFalse(utils.use_redis(), "Using redis should be disabled")

        utils.get_settings().use_redis = True
        self.assertTrue(utils.use_redis(), "Using redis should be enabled")


class TestExtractRestApiEndpoint(BaseRedisTest):
    def setUp(self):
        super().setUp()
        self.portal_url = self.portal.absolute_url()
        self.endpoint = f"{self.portal_url}/@elasticsearch_extractdata"

        self.api_session = RelativeSession(self.portal_url)
        self.api_session.headers.update({"Accept": "application/json"})
        self.api_session.auth = (SITE_OWNER_NAME, SITE_OWNER_PASSWORD)

        self.obj = api.content.create(
            self.portal,
            "Document",
            "page",
            title="New Content",
            text=RichTextValue("<p>abc</p>"),
        )
        transaction.commit()

    def tearDown(self):
        self.api_session.close()

    def test_extract_all_data_via_endpoint(self):
        params = {"uuid": self.obj.UID()}
        response = self.api_session.get(self.endpoint, params=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/json")
        self.assertEqual(self.endpoint, response.json()["@id"])
        content = response.json()["data"]
        processor = self.get_processor()

        self.maxDiff = None
        self.assertDictEqual(
            json.loads(json.dumps(processor.get_data_for_es(self.obj.UID()))), content
        )

    def test_extract_certain_attributes_via_endpoint(self):
        params = {
            "uuid": self.obj.UID(),
            "attributes:list": ["SearchableText", "Title", "id"],
        }
        response = self.api_session.get(self.endpoint, params=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/json")
        self.assertEqual(self.endpoint, response.json()["@id"])
        content = response.json()["data"]
        processor = self.get_processor()

        self.maxDiff = None
        self.assertDictEqual(
            json.loads(
                json.dumps(
                    processor.get_data_for_es(
                        self.obj.UID(),
                        attributes=params["attributes:list"],
                    )
                )
            ),
            content,
        )

    def test_404_if_obj_not_found(self):
        response = self.api_session.get(self.endpoint, params={"uuid": "dummy-uid"})
        self.assertEqual(response.status_code, 404)

    def test_extract_endoint_respects_view_permission(self):

        api_session = RelativeSession(self.portal_url)
        api_session.headers.update({"Accept": "application/json"})

        self.obj.manage_permission("View", roles=[])
        transaction.commit()

        params = {"uuid": self.obj.UID()}
        response = self.api_session.get(self.endpoint, params=params)
        self.assertEqual(response.status_code, 401)
