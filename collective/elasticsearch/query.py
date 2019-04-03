# -*- coding: utf-8 -*-
from collective.elasticsearch.indexes import EZCTextIndex
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.interfaces import IQueryAssembler
from collective.elasticsearch.utils import getESOnlyIndexes
from zope.interface import implementer


@implementer(IQueryAssembler)
class QueryAssembler(object):

    def __init__(self, request, es):
        self.es = es
        self.catalogtool = es.catalogtool
        self.request = request

    def normalize(self, query):
        sort_on = []
        sort = query.pop('sort_on', None)
        # default plone is ascending
        sort_order = query.pop('sort_order', 'asc')
        if sort_order in ('descending', 'reverse', 'desc'):
            sort_order = 'desc'
        else:
            sort_order = 'asc'

        if sort:
            for sort_str in sort.split(','):
                sort_on.append({
                    sort_str: {"order": sort_order}
                })
        sort_on.append('_score')
        if 'b_size' in query:
            del query['b_size']
        if 'b_start' in query:
            del query['b_start']
        if 'sort_limit' in query:
            del query['sort_limit']
        return query, sort_on

    def __call__(self, dquery):
        filters = []
        catalog = self.catalogtool._catalog
        idxs = catalog.indexes.keys()
        query = {'match_all': {}}
        es_only_indexes = getESOnlyIndexes()
        for key, value in dquery.items():
            if key not in idxs and key not in es_only_indexes:
                continue

            index = getIndex(catalog, key)
            if index is None and key in es_only_indexes:
                # deleted index for plone performance but still need on ES
                index = EZCTextIndex(catalog, key)

            qq = index.get_query(key, value)
            if qq is None:
                continue

            if index is not None and index.filter_query:
                filters.append(qq)
            else:
                query = qq
        if len(filters) == 0:
            return query
        else:
            return {
                'filtered': {
                    'filter': {
                        'and': filters
                    },
                    'query': query
                }
            }
