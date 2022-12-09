from collective.elasticsearch import utils
from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.tests import BaseRedisTest
from plone import api
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.textfield import RichTextValue
from plone.dexterity.fti import DexterityFTIModificationDescription
from plone.dexterity.fti import ftiModified
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from plone.restapi.testing import RelativeSession
from unittest import mock
from zope.lifecycleevent import ObjectModifiedEvent

import io
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


class TestIndexBlobs(BaseRedisTest):
    def setUp(self):
        super().setUp()

    def _setup_sample_file(self):
        file_path = os.path.join(os.path.dirname(__file__), "assets/test.pdf")
        with io.FileIO(file_path, "rb") as pdf:
            _file = api.content.create(
                container=api.portal.get(),
                type="File",
                id="test-file",
                file=NamedBlobFile(data=pdf.read(), filename="test.pdf"),
            )
        self.commit(wait=1)
        return _file

    def _set_model_file(self, fti, path_to_xml):
        fti.model_file = path_to_xml
        ftiModified(
            fti,
            ObjectModifiedEvent(
                fti, DexterityFTIModificationDescription("model_file", "")
            ),
        )

    def test_index_data_from_file(self):
        self._setup_sample_file()
        query = {"SearchableText": "text"}
        cat_results = self.catalog._old_searchResults(**query)
        self.assertEqual(0, len(cat_results), "Expect no result")
        es_results = self.catalog(**query)
        self.assertEqual(1, len(es_results), "Expect 1 item")

    def test_update_and_delete_file(self):
        file_ = self._setup_sample_file()
        file_path = os.path.join(os.path.dirname(__file__), "assets/test2.docx")
        with io.FileIO(file_path, "rb") as word:
            file_.file = NamedBlobFile(data=word.read(), filename="test2.docx")
            file_.reindexObject()
        self.commit(wait=1)

        query = {"SearchableText": "Lorem"}
        es_results = self.catalog(**query)
        self.assertEqual(1, len(es_results), "Expect 1 item")

        self.portal.manage_delObjects(ids=[file_.getId()])
        self.commit(wait=1)

        query = {"SearchableText": "lorem"}
        es_results = self.catalog(**query)
        self.assertEqual(0, len(es_results), "Expect no item")

    def test_make_sure_binary_data_are_removed_from_es(self):
        file_ = self._setup_sample_file()
        es_data = self.es.connection.get(self.es.index_name, file_.UID())
        self.assertIsNone(es_data["_source"]["attachments"][0]["data"])

    def test_multiple_file_fields(self):
        fti = self.portal.portal_types.File
        self._set_model_file(fti, "collective.elasticsearch.tests:test_file_schema.xml")
        file_path_1 = os.path.join(os.path.dirname(__file__), "assets/test.pdf")
        file_path_2 = os.path.join(os.path.dirname(__file__), "assets/test2.docx")
        with io.FileIO(file_path_1, "rb") as pdf, io.FileIO(file_path_2, "rb") as word:
            file_ = api.content.create(
                container=api.portal.get(),
                type="File",
                id="test-file-multiple-file-fields",
                file=NamedBlobFile(data=pdf.read(), filename="test.pdf"),
                file2=NamedBlobFile(data=word.read(), filename="test2.docx"),
            )
        self.commit(wait=1)

        query = {"SearchableText": "lorem"}
        es_results = self.catalog(**query)
        self.assertEqual(1, len(es_results), "Expect 1 item")

        query = {"SearchableText": "text"}
        es_results = self.catalog(**query)
        self.assertEqual(1, len(es_results), "Expect 1 item")

        es_data = self.es.connection.get(self.es.index_name, file_.UID())
        self.assertIsNone(es_data["_source"]["attachments"][0]["data"])
        self.assertIsNone(es_data["_source"]["attachments"][1]["data"])

        file_.file2 = None
        file_.reindexObject()
        self.commit(wait=1)

        query = {"SearchableText": "lorem"}
        es_results = self.catalog(**query)
        self.assertEqual(0, len(es_results), "Expect 0 item")

        self._set_model_file(fti, "plone.app.contenttypes.schema:file.xml")

    def test_dont_queue_blob_extraction_jobs_if_not_possible(self):
        settings = {"index": {"default_pipeline": None}}
        self.es.connection.indices.put_settings(body=settings, index=self.es.index_name)
        self.es.connection.ingest.delete_pipeline("cbor-attachments")
        file_path = os.path.join(os.path.dirname(__file__), "assets/test2.docx")
        with io.FileIO(file_path, "rb") as pdf:
            self._file = api.content.create(
                container=api.portal.get(),
                type="File",
                id="test-file2",
                file=NamedBlobFile(data=pdf.read(), filename="test2.docx"),
            )
        self.commit(wait=1)

        query = {"SearchableText": "lorem"}
        es_results = self.catalog(**query)
        self.assertEqual(0, len(es_results), "Expect 0 item")

    def test_do_not_index_data_from_images(self):
        file_path = os.path.join(os.path.dirname(__file__), "assets/image.png")
        with io.FileIO(file_path, "rb") as image:
            _image = api.content.create(
                container=api.portal.get(),
                type="Image",
                id="test-file",
                image=NamedBlobImage(data=image.read(), filename="image.png"),
            )
        self.commit(wait=1)

        es_data = self.es.connection.get(self.es.index_name, _image.UID())
        self.assertNotIn(
            "attachments",
            es_data["_source"],
            "Expect not attachments on es data for a image",
        )
