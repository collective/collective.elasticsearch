from collective.elasticsearch import logger


def BrainFactory(catalog):
    def factory(result):
        path = result.get("fields", {}).get("path.path", None)
        if type(path) in (list, tuple, set) and len(path) > 0:
            path = path[0]
        if path:
            rid = catalog.uids.get(path)
            try:
                return catalog[rid]
            except TypeError:
                logger.error(f"Got not integer key for result: {result}")
                return None
            except KeyError:
                logger.error(f"Couldn't get catalog entry for result: {result}")
                return None
        return None

    return factory
