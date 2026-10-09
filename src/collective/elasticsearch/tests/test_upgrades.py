from collective.elasticsearch.tests import BaseFunctionalTest
from collective.elasticsearch.upgrades import update_attachment_pipeline


class TestUpdateAttachmentPipeline(BaseFunctionalTest):
    def test_pipeline_removes_binary_data_after_upgrade(self):
        conn = self.es.connection
        conn.ingest.put_pipeline(id="cbor-attachments", processors=[])
        update_attachment_pipeline(self.portal)
        pipeline = conn.ingest.get_pipeline(id="cbor-attachments")["cbor-attachments"]
        attachment = pipeline["processors"][0]["foreach"]["processor"]["attachment"]
        self.assertTrue(
            attachment["remove_binary"],
            "The upgraded pipeline must remove the binary data",
        )
