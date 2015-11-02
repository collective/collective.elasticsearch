from zope.interface import Interface
from zope import schema


class IElasticSearchLayer(Interface):
    pass


class IElasticSearchCatalog(Interface):
    pass


class IMappingProvider(Interface):
    def __call__():
        pass


class IAdditionalIndexDataProvider(Interface):
    def __call__():
        pass


class IQueryAssembler(Interface):
    def normalize(query):
        pass

    def __call__(dquery):
        pass


class IElasticSettings(Interface):

    hosts = schema.List(
        title=u'Hosts',
        default=[u'127.0.0.1'],
        unique=True,
        value_type=schema.TextLine(title=u'Host'))

    enabled = schema.Bool(
        title=u'Enabled',
        default=False
    )

    sniff_on_start = schema.Bool(
        title=u'Sniff on start',
        default=False)

    sniff_on_connection_fail = schema.Bool(
        title=u'Sniff on connection fail',
        default=False)

    sniffer_timeout = schema.Float(
        title=u'Sniffer timeout',
        default=0.1)

    retry_on_timeout = schema.Bool(
        title=u'Retry on timeout',
        default=True)

    timeout = schema.Float(
        title=u'Read timeout',
        description=u'how long before timeout connecting to elastic search',
        default=2.0)

    auto_flush = schema.Bool(
        title=u'Auto flush',
        description=u'Should indexing operations in elastic search '
                    u'be immediately consistent. '
                    u'If on, things are always updated immediately at '
                    u'a cost of performance.',
        default=True)

    bulk_size = schema.Int(
        title=u'Bulk Size',
        description=u'bulk size for elastic queries',
        default=50)
