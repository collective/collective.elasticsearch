from Products.CMFPlone.browser import search


class Search(search.Search):

    def munge_search_term(self, q):
        # We don't want to munge search terms for
        # EL
        return q