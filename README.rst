Introduction
============

See the full documentation on `readthedocs <http://collectiveelasticsearch.readthedocs.io/>`_.

Install elasticsearch
---------------------

Less than 5 minutes:
    - Download & install Java
    - Download & install Elastic Search
    - bin/elasticsearch

Step by Step for Ubuntu:
    - add-apt-repository ppa:webupd8team/java
    - apt-get update
    - apt-get install git curl oracle-java7-installer
    - curl -O https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-2.4.3.tar.gz
    - tar xfvz elasticsearch-2.4.3.tar.gz
    - cd elasticsearch
    - bin/elasticsearch &

Does it work?
    - curl http://localhost:9200/
    - Do you see the Hudsucker Proxy reference? "You Know, for Search"

Use Elastic Search in Plone:
    - Add collective.elasticsearch to eggs & re-run buildout
    - Restart Plone
    - Goto Control Panel
    - Add "Eleastic Search" in Add-on Products
    - Click "Elastic Search" in "Add-on Configuration"
    - Enable
    - Click "Convert Catalog"
    - Click "Rebuild Catalog"

You now have a insanely scalable modern search engine. Now live the life of the Mind!

Overview
--------

This package aims to index all fields the portal_catalog indexes
and allows you to delete the `Title`, `Description` and `SearchableText`
indexes which can provide significant improvement to performance and RAM usage.

Then, ElasticSearch queries are ONLY used when Title, Description and SearchableText
text are in the query. Otherwise, the plone's default catalog will be used.
This is because Plone's default catalog is faster on normal queries than using
ElasticSearch.

Boosting an Index
-----------------

You can boost an individual index and control which indexes are searched from
the control panel. This is done by placing a colon and a number after the
index. eg:

```
Description:5
Title: 20
SearchableText:0
```


Compatibility
-------------

Only tested with Plone 5 with Dexterity types.

It should also work with Plone 4.3 and archetypes.

Deployed with Elasticsearch 2.4.3

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


TODO
----

- Spellcheck
- Custom Similarity
- Faceting


Travis
------

.. image:: https://travis-ci.org/collective/collective.elasticsearch.png
   :target: https://travis-ci.org/collective/collective.elasticsearch
   :alt: Travis CI
