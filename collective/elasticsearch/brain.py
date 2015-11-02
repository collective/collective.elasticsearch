

def BrainFactory(catalog):
    def factory(result):
        path = result.get('fields', {}).get('path.path', None)
        if type(path) in (list, tuple, set) and len(path) > 0:
            path = path[0]
        if path:
            rid = catalog.uids.get(path)
            try:
                return catalog[rid]
            except:
                return None
    return factory
