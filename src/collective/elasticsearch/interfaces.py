from dataclasses import dataclass
from Products.CMFCore.interfaces import IIndexQueueProcessor
from typing import Dict
from typing import List
from typing import Tuple
from zope import schema
from zope.interface import Interface
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
@@
     raise_search_exception = schema.Bool(
         title="Raise Search Exceptions",
         description="If there is an error with elastic search Plone will default to trying the old catalog search. Set this to true to raise the error instead.",
         default=False,
         required=False,
     )

     # choice of python client to use for the configured cluster
     SearchClientVocabulary = SimpleVocabulary(
         [
             SimpleTerm("elasticsearch", "elasticsearch", "Elasticsearch (elasticsearch-py)"),
             SimpleTerm("opensearch", "opensearch", "OpenSearch (opensearch-py)"),
         ]
     )

     search_client = schema.Choice(
         title="Search client backend",
         description="Select which Python client to use to talk to the search cluster.",
         vocabulary=SearchClientVocabulary,
         default="elasticsearch",
         required=True,
     )
*** End Patch