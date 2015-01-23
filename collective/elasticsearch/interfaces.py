from zope.interface import Interface
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

DISABLE_MODE = 'disabled'
REPLACEMENT_MODE = 'replacement'
DUAL_MODE = 'dual'


class IElasticSearchCatalog(Interface):
    '''
    Interface if elastic search catalog is allowed
    '''


class IElasticSettings(Interface):

    hosts = schema.List(
        title=u'Hosts',
        default=[u'127.0.0.1'],
        unique=True,
        value_type=schema.TextLine(title=u'Host'))

    mode = schema.Choice(
        title=u'Mode',
        description=u'Which mode elastic search should operate in. '
                    u'Changing this setting might require you to '
                    u'reindex the catalog. ',
        default=DISABLE_MODE,
        vocabulary=SimpleVocabulary([
            SimpleTerm(DISABLE_MODE, DISABLE_MODE, u'Disabled'),
            SimpleTerm(REPLACEMENT_MODE, REPLACEMENT_MODE, u'Replace catalog'),
            SimpleTerm(
                DUAL_MODE, DUAL_MODE,
                u'Index plone and elastic search but still '
                u'search with elastic'),
        ]))

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
        default=0.5)

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
