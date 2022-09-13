from zope import schema
from zope.interface import Interface


class IElasticSearchLayer(Interface):
    pass


class IElasticSearchCatalog(Interface):
    pass


class IMappingProvider(Interface):
    def get_index_creation_body():  # NOQA E0211
        pass

    def __call__():  # NOQA E0211
        pass


class IAdditionalIndexDataProvider(Interface):
    def __call__():  # NOQA E0211
        pass


class IReindexActive(Interface):
    pass


class IQueryAssembler(Interface):
    def normalize(query):  # NOQA E0213
        pass

    def __call__(query):  # NOQA E0213
        pass


class IElasticSettings(Interface):
    hosts = schema.List(
        title="Hosts",
        default=["127.0.0.1"],
        unique=True,
        value_type=schema.TextLine(title="Host"),
    )

    enabled = schema.Bool(title="Enabled", default=False)

    es_only_indexes = schema.Set(
        title="Indexes for which all searches are done through ElasticSearch",
        default={"Title", "Description", "SearchableText"},
        value_type=schema.TextLine(title="Index"),
    )

    sniff_on_start = schema.Bool(title="Sniff on start", default=False)

    sniff_on_connection_fail = schema.Bool(
        title="Sniff on connection fail", default=False
    )

    sniffer_timeout = schema.Float(
        title="Sniffer timeout", required=False, default=None
    )

    retry_on_timeout = schema.Bool(title="Retry on timeout", default=True)

    timeout = schema.Float(
        title="Read timeout",
        description="how long before timeout connecting to elastic search",
        default=2.0,
    )

    bulk_size = schema.Int(
        title="Bulk Size", description="bulk size for elastic queries", default=50
    )
