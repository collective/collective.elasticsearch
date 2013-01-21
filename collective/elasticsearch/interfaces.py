from zope.interface import Interface
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

DISABLE_MODE = 'disabled'
REPLACEMENT_MODE = 'replacement'
DUAL_MODE = 'dual'


class IElasticSearchCatalog(Interface):
    """
    Interface if elastic search catalog is allowed
    """


class IElasticSettings(Interface):

    connection_string = schema.TextLine(
        title=u'Connection string',
        default=u'127.0.0.1:9200')

    mode = schema.Choice(
        title=u'Mode',
        description=u'Which mode elastic search should operate in. '
                    u'Changing this setting might require you to '
                    u'reindex the catalog. ',
        default=DISABLE_MODE,
        vocabulary=SimpleVocabulary([
            SimpleTerm(DISABLE_MODE, DISABLE_MODE, u'Disabled'),
            SimpleTerm(REPLACEMENT_MODE, REPLACEMENT_MODE, u'Replace catalog'),
            SimpleTerm(DUAL_MODE, DUAL_MODE,
                u'Index plone and elastic search but still '
                u'search with elastic'),
        ]))

    auto_flush = schema.Bool(
        title=u'Auto flush',
        description=u"Should indexing operations in elastic search "
                    u"be immediately consistent. "
                    u"If on, things are always updated immediately at "
                    u"a cost of performance.",
        default=True)
