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
        - curl -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-6.3.0.tar.gz
        - tar xfvz elasticsearch-6.3.0.tar.gz
        - cd elasticsearch
        - bin/elasticsearch &

Does it work?
    - curl http://localhost:9200/
    - Do you see the Hudsucker Proxy reference? "You Know, for Search"

Use Elastic Search in Plone:
    - Add collective.elasticsearch to eggs & re-run buildout
    - Restart Plone
    - Goto Control Panel
    - Add "Elastic Search" in Add-on Products
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
text are in the query. Otherwise, Plone's default catalog will be used.
This is because Plone's default catalog is faster on normal queries than using
ElasticSearch.


Compatibility
-------------

Only tested with Plone 5 with Dexterity types.

It should also work with Plone 4.3 and archetypes.

Deployed with Elasticsearch 6.3.0

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


Running tests
-------------

Run elasticsearch for tests to utilize:

    docker run \
        -e "cluster.name=docker-cluster" \
        -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
        -p 9200:9200 \
        docker.elastic.co/elasticsearch/elasticsearch-oss:6.3.0

Then, you can use one of the travis buildout test files:

    python bootstrap.py -c travis-5.0.cfg
    ./bin/buildout -c travis-5.0.cfg
    ./bin/test -s collective.elasticsearch


Travis
------

.. image:: https://travis-ci.org/collective/collective.elasticsearch.png
   :target: https://travis-ci.org/collective/collective.elasticsearch
   :alt: Travis CI
