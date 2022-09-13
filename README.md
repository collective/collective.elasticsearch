<h1 align="center">collective.elasticsearch</h1>

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/collective.elasticsearch)](https://pypi.org/project/collective.elasticsearch/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/collective.elasticsearch)](https://pypi.org/project/collective.elasticsearch/)
[![PyPI - Wheel](https://img.shields.io/pypi/wheel/collective.elasticsearch)](https://pypi.org/project/collective.elasticsearch/)
[![PyPI - License](https://img.shields.io/pypi/l/collective.elasticsearch)](https://pypi.org/project/collective.elasticsearch/)
[![PyPI - Status](https://img.shields.io/pypi/status/collective.elasticsearch)](https://pypi.org/project/collective.elasticsearch/)


[![PyPI - Plone Versions](https://img.shields.io/pypi/frameworkversions/plone/collective.elasticsearch)](https://pypi.org/project/collective.elasticsearch/)

[![Code analysis checks](https://github.com/collective/collective.elasticsearch/actions/workflows/code-analysis.yml/badge.svg)](https://github.com/collective/collective.elasticsearch/actions/workflows/code-analysis.yml)
[![Tests](https://github.com/collective/collective.elasticsearch/actions/workflows/tests.yml/badge.svg)](https://github.com/collective/collective.elasticsearch/actions/workflows/tests.yml)
![Code Style](https://img.shields.io/badge/Code%20Style-Black-000000)

[![GitHub contributors](https://img.shields.io/github/contributors/collective/collective.elasticsearch)](https://github.com/collective/collective.elasticsearch)
[![GitHub Repo stars](https://img.shields.io/github/stars/collective/collective.elasticsearch?style=social)](https://github.com/collective/collective.elasticsearch)

</div>

## Introduction

This package aims to index all fields the portal_catalog indexes and allows you to delete the `Title`, `Description` and `SearchableText` indexes which can provide significant improvement to performance and RAM usage.

Then, ElasticSearch queries are ONLY used when Title, Description and SearchableText text are in the query. Otherwise, the plone's default catalog will be used. This is because Plone's default catalog is faster on normal queries than using ElasticSearch.


## Install Elastic Search

For a comprehensive documentation about the different options of installing Elastic Search, please read [their documentation](https://www.elastic.co/guide/en/elasticsearch/reference/7.7/install-elasticsearch.html).

A quick start, using Docker would be:

```shell
docker run \
		-e "discovery.type=single-node" \
		-e "cluster.name=docker-cluster" \
		-e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
		-p 9200:9200 \
		elasticsearch:7.7.0
```

### Test the installation

Run, on your shell:

```shell
curl http://localhost:9200/
```
And you should see the Hudsucker Proxy reference? "You Know, for Search"

## Install collective.elasticsearch

First, add `collective.elasticsearch` to your package dependencies, or install it with `pip` (the same one used by your Plone installation):

```shell
pip install collective.elasticsearch
```

Restart Plone, and go to the `Control Panel`, click in `Add-ons`, and select `Elastic Search`.

Now, go to `Add-on Configuration` and:

- Check "Enable"
- Click "Convert Catalog"
- Click "Rebuild Catalog"

You now have a insanely scalable modern search engine. Now live the life of the Mind!


## Compatibility

- Python 3
- Plone 5.2 and above
- Tested with Elastic Search 7.7.0

## State

Support for all index column types is done EXCEPT for the DateRecurringIndex index column type. If you are doing a full text search along with a query that contains a DateRecurringIndex column, it will not work.


## Celery support

This package comes with Celery support where all indexing operations will be pushed into celery to be run asynchronously.

Please see instructions for `collective.celery` to see how this works.

## Developing this package

Create the virtual enviroment and install all dependencies:

```shell
make build
```

Start Plone in foreground:

```shell
make start
```


### Running tests

```shell
make tests
```


### Formatting the codebase

```shell
make format
```

### Linting the codebase

```shell
make lint
```

## License

The project is licensed under the GPLv2.
