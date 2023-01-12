from dataclasses import dataclass
from Products.CMFCore.interfaces import IIndexQueueProcessor
from typing import Dict
from typing import List
from typing import Tuple
from zope import schema
from zope.interface import Interface


class IElasticSearchLayer(Interface):
    pass


class IElasticSearchManager(Interface):
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

    enabled = schema.Bool(title="Enabled", default=False, required=False)

    use_redis = schema.Bool(
        title="Use redis as queue",
        description=(
            "You can enable this option if you have installed redis, "
            "set the necessary env variables and started a worker."
            "Please check the README for more informations"
        ),
        default=False,
        required=False,
    )

    hosts = schema.List(
        title="Hosts",
        default=["127.0.0.1"],
        unique=True,
        value_type=schema.TextLine(title="Host"),
    )

    es_only_indexes = schema.Set(
        title="Indexes for which all searches are done through ElasticSearch",
        default={"Title", "Description", "SearchableText"},
        value_type=schema.TextLine(title="Index"),
    )

    sniff_on_start = schema.Bool(title="Sniff on start", default=False, required=False)

    sniff_on_connection_fail = schema.Bool(
        title="Sniff on connection fail", default=False, required=False
    )

    sniffer_timeout = schema.Float(
        title="Sniffer timeout", required=False, default=None
    )

    retry_on_timeout = schema.Bool(
        title="Retry on timeout", default=True, required=False
    )

    timeout = schema.Float(
        title="Read timeout",
        description="how long before timeout connecting to elastic search",
        default=2.0,
    )

    bulk_size = schema.Int(
        title="Bulk Size", description="bulk size for elastic queries", default=50
    )

    highlight = schema.Bool(
        title="Enable Search Highlight",
        description="Use elasticsearch highlight feature instead of descriptions in search results",
        default=False,
        required=False,
    )

    highlight_threshold = schema.Int(
        title="Highlight Threshold",
        description="Number of highlighted characters to display in search results descriptions",
        default=600,
        required=False,
    )

    highlight_pre_tags = schema.Text(
        title="Highlight pre tags",
        description='Used with highlight post tags to wrap matching words. e.g. &lt;pre class="highlight"&gt;. One tag per line',
        default="",
        required=False,
    )

    highlight_post_tags = schema.Text(
        title="Higlight post tags",
        description="Used with highlight pre tags to wrap matching words. e.g. &lt;/pre&gt; One tag per line",
        default="",
        required=False,
    )

    raise_search_exception = schema.Bool(
        title="Raise Search Exceptions",
        description="If there is an error with elastic search Plone will default to trying the old catalog search. Set this to true to raise the error instead.",
        default=False,
        required=False
    )


class IElasticSearchIndexQueueProcessor(IIndexQueueProcessor):
    """Index queue processor for elasticsearch."""


@dataclass
class IndexingActions:

    index: Dict[str, dict]
    reindex: Dict[str, dict]
    unindex: Dict[str, dict]
    index_blobs: Dict[str, dict]
    uuid_path: Dict[str, str]

    def __len__(self):
        size = 0
        size += len(self.index)
        size += len(self.reindex)
        size += len(self.unindex)
        return size

    def all(self) -> List[Tuple[str, str, Dict]]:
        all_data = []
        for attr, action in (
            ("index", "index"),
            ("reindex", "update"),
            ("unindex", "delete"),
        ):
            action_data = [
                (uuid, data) for uuid, data in getattr(self, attr, {}).items()
            ]
            if action_data:
                all_data.extend([(action, uuid, data) for uuid, data in action_data])
        return all_data

    def all_blob_actions(self):
        return [(uuid, data) for uuid, data in getattr(self, "index_blobs", {}).items()]
