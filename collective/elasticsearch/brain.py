

def BrainFactory(catalog):
    def factory(result):
        path = result.get('path', {}).get('path', None)
        if path:
            rid = catalog.uids.get(path)
            return catalog[rid]
    return factory
