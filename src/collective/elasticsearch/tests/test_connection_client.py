import pytest


def test_get_connection_settings_respects_search_client(monkeypatch):
    import collective.elasticsearch.utils as utils

    class FakeSettings:
        hosts = ["http://127.0.0.1:9200"]
        retry_on_timeout = True
        sniff_on_connection_fail = False
        sniff_on_start = False
        sniffer_timeout = None
        timeout = 2.0
        search_client = "opensearch"

    monkeypatch.setattr(utils, "get_settings", lambda: FakeSettings())
    hosts, params = utils.get_connection_settings()
    assert hosts == ["http://127.0.0.1:9200"]
    assert params["client"] == "opensearch"
    assert params["timeout"] == 2.0
