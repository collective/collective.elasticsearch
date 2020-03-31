.. collective.elasticsearch documentation master file, created by
   sphinx-quickstart on Mon Mar 13 15:04:25 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to collective.elasticsearch's documentation!
====================================================

Overview
--------

This package aims to index all fields the portal_catalog indexes
and allows you to delete the `Title`, `Description` and `SearchableText`
indexes which can provide significant improvement to performance and RAM usage.

Then, ElasticSearch queries are ONLY used when Title, Description and SearchableText
text are in the query. Otherwise, the plone's default catalog will be used.
This is because Plone's default catalog is faster on normal queries than using
ElasticSearch.


Compatibility
-------------

Only unit tested with Plone 5 with Dexterity types and archetypes.

It should also work with Plone 4.3 and Plone 5.1.

Deployed with Elasticsearch 7.6.0

State
-----

Support for all index column types is done EXCEPT for the DateRecurringIndex
index column type. If you are doing a full text search along with a query that
contains a DateRecurringIndex column, it will not work.


Celery support
--------------

This package comes with Celery support where all indexing operations will be pushed
into celery to be run asynchronously.

Please see instructions for collective.celery to see how this works.

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
