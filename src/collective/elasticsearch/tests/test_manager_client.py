import collective.elasticsearch.manager as manager
import collective.elasticsearch.utils as utils
import collective.elasticsearch.local as local


def test_manager_uses_opensearch_when_selected(monkeypatch):
    # fake settings selection
    monkeypatch.setattr(utils, "get_connection_settings", lambda: (["http://host:9200"], {"client": "opensearch"}))

    created = {}

    class FakeOpenSearch:
        def __init__(self, hosts, **params):
            created['client'] = 'opensearch'
            self.hosts = hosts
            self.params = params

        def ping(self):
            return True

    # ensure OpenSearch is available in module under test
    monkeypatch.setattr(manager, "OpenSearch", FakeOpenSearch)
    # ensure Elasticsearch fallback exists
    class FakeElasticsearch:
        def __init__(self, hosts, **params):
            created['client'] = 'elasticsearch'

        def ping(self):
            return True

    monkeypatch.setattr(manager, "Elasticsearch", FakeElasticsearch)

    # clear any existing cached client
    try:
        delattr(local.localData, manager.ElasticSearchManager.connection_key)
    except Exception:
        pass

    m = manager.ElasticSearchManager()
    conn = m.connection
    assert created["client"] == "opensearch"
    assert hasattr(conn, "ping")


def test_manager_recreates_when_ping_fails(monkeypatch):
    # initial get_connection_settings returns elasticsearch
    monkeypatch.setattr(utils, "get_connection_settings", lambda: (["h"], {"client": "elasticsearch"}))

    class DeadClient:
        def ping(self):
            return False

    class FreshClient:
        def __init__(self, hosts, **params):
            self.hosts = hosts

        def ping(self):
            return True

    # monkeypatch classes
    monkeypatch.setattr(manager, "Elasticsearch", DeadClient)
    monkeypatch.setattr(manager, "OpenSearch", None)

    # force the cached dead client
    local.set_local(manager.ElasticSearchManager.connection_key, DeadClient())

    # now change get_connection_settings to return fresh creation params and set Elasticsearch init to FreshClient
    monkeypatch.setattr(utils, "get_connection_settings", lambda: (["h"], {"client": "elasticsearch"}))
    monkeypatch.setattr(manager, "Elasticsearch", FreshClient)

    m = manager.ElasticSearchManager()
    conn = m.connection
    assert isinstance(conn, FreshClient)
    assert conn.ping()
