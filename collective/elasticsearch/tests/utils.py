

def flush_queue():
    try:
        from Products.CMFCore.indexing import processQueue
        processQueue()
    except ImportError:
        pass
