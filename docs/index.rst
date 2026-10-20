.. collective.elasticsearch documentation master file, created by
   sphinx-quickstart on Mon Mar 13 15:04:25 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to collective.elasticsearch's documentation!
====================================================

Overview
--------

This package indexes all fields the portal_catalog indexes into
Elasticsearch and allows you to delete the ``Title``, ``Description`` and
``SearchableText`` indexes from the catalog, which can provide significant
improvement to performance and RAM usage.

Content is indexed through the Plone indexing queue. Searching elasticsearch
is explicit, catalog queries are never routed to elasticsearch::

    from collective.elasticsearch.manager import ElasticSearchManager

    results = ElasticSearchManager().secure_search({"SearchableText": "foo"})

``secure_search`` restricts the results like the catalog's ``searchResults``
does, ``search`` runs a query unrestricted. The elasticsearch only indexes
setting (``Title``, ``Description`` and ``SearchableText`` by default) still
controls which attributes are indexed into elasticsearch on top of the
catalog indexes, and those keys stay queryable in elasticsearch even after
the indexes were deleted from the portal_catalog.

Maintenance
-----------

The control panel offers three actions:

- **Convert Catalog**: creates the elasticsearch index, maps all catalog
  indexes and enables indexing into elasticsearch. Run it once after
  installing and after mapping changes.
- **Rebuild Elasticsearch Index**: recreates the elasticsearch index from
  the objects in the catalog. The ZCatalog is not modified. Run it when the
  elasticsearch index is lost or outdated.
- **Synchronize**: compares the UIDs in the catalog with the documents in
  elasticsearch, indexes missing objects and deletes documents without a
  catalog entry. Run it to fix drift without a full rebuild.

The ZMI catalog maintenance ("Clear and Rebuild", "Clear", the "Catalog"
button and ``refreshCatalog``) only operates on the ZCatalog and does not
reach elasticsearch. The ZMI "Remove" on the Catalog tab does delete the
selected records from elasticsearch, once the transaction committed.
Reordering content does not update ``getObjPositionInParent`` in
elasticsearch, the indexed value is the position at the time the object was
last indexed.

Compatibility
-------------

- Python 3.10+
- Plone 6.0, 6.1 and 6.2
- Elasticsearch 8.x

State
-----

Support for all index column types is done EXCEPT for the DateRecurringIndex
index column type. If you are doing a full text search along with a query that
contains a DateRecurringIndex column, it will not work.

Contents:

.. toctree::
   :maxdepth: 2

   install
   config
   history



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
