from collective.elasticsearch.indexes import getIndex


class QueryAssembler(object):

    def __init__(self, catalogtool):
        self.catalogtool = catalogtool
        self.request = catalogtool.REQUEST

    def normalize(self, query):
        sort_on = ['_score']
        sort = query.pop('sort_on', None)
        if sort:
            sort_on.extend(sort.split(','))
        sort_order = query.pop('sort_order', 'ascending')
        if sort_on:
            sortstr = ','.join(sort_on)
            if sort_order in ('descending', 'reverse', 'desc'):
                sortstr += ':desc'
            else:
                sortstr += ':asc'
        else:
            sortstr = ''
        if 'b_size' in query:
            del query['b_size']
        if 'b_start' in query:
            del query['b_start']
        if 'sort_limit' in query:
            del query['sort_limit']
        return query, sortstr

    def __call__(self, dquery):
        filters = []
        catalog = self.catalogtool._catalog
        idxs = catalog.indexes.keys()
        query = {'match_all': {}}
        for key, value in dquery.items():
            if key not in idxs:
                continue
            index = getIndex(catalog, key)
            if index is None:
                continue
            qq = index.get_query(key, value)
            if qq is None:
                continue
            if type(qq) == tuple:
                qq, is_query = qq
            else:
                is_query = False
            if is_query:
                query = qq
            else:
                filters.append(qq)
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
