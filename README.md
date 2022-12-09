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


## Redis queue integration with blob indexing support

### TLDR

```shell
docker-compose -f docker-compose.dev.yaml up -d
```

Your Plone site should be up and running: http://localhost:8080/Plone

- Go to `Add-on Configuration`
- Check "Enable"
- Click "Convert Catalog"
- Click "Rebuild Catalog"

### Why

Having a queue, which does heavy and time consuming jobs asynchronous improves the responsiveness of the website and lowers
the risk of having database conflicts. This implementation aims to have an almost zero impact in terms of performance for any given plone
installation or given installation using collective.elasticsearch already

### How does it work

- Instead of index/reindex/unindex data while committing to the DB, jobs are added to a queue in a after commit hook.
- No data is extracted from any object, this all happens later
- One or multiple worker execute jobs, which gather the necessary data via the RestAPI.
- The extraction of the data and the indexing in elasticsearch happens via queue.

Workflow:

1. Content gets created/updated
2. Commit Data to DB + Update Plone Catalog
3. Via after commit hooks jobs are getting created
4. Website is ready to use again - Request is done
5. Worker get initialized
6. A job collects values to index via plone RestAPI and indexes those values on elasticsearch

There are two queues. One for normal indexing jobs and one for the heavy lifting to index binaries.
Jobs from the second queue only gets pulled if the normal indexing queue is empty.

Trade of: Instead of a fully indexed document in elasticsearch we have pretty fast at least one there.

### Requirements

There are a couple things that need to be done manually if you want redis queue support.


1. Install redis extra from collective.elasticsearch
```shell
pip install collective.elasticsearch[redis]
```


2. Install ingest-attachment plugin for elasticsearch - by default the elasticsearch image does not have any plugins installed.

```shell
docker exec CONTAINER_NAME /bin/sh -c "bin/elasticsearch-plugin install ingest-attachment -b"; \
docker restart CONTAINER_NAME
```

The container needs to be restarted, otherwise the plugin is not available

3. Communication between Redis Server, Plone and Redis worker is configured in environment variables.

```shell
export PLONE_REDIS_DSN=redis://localhost:6379/0
export PLONE_BACKEND=http://localhost:8080/Plone
export PLONE_USERNAME=admin
export PLONE_PASSWORD=admin
```
This is a example configuration for local development only.
You can use the `start-redis-support` command to spin up a plone instance with the environment variables already set

```shell
make start-redis-support
```

4. Start a Redis Server

Start your own or use the `start-redis` command
```shell
make redis
```

5. start a redis worker

The redis worker does the "job" and indexes everything via two queues:

- normal: Normal indexing/reindexing/unindexing jobs - Does basically the same thing as without redis support, but well yeah via a queue.
- low: Holds jobs for expensive blob indexing

The priority is handled by the python-rq worker.

The rq worker needs to be started with the same environment variables present as described in 3. 

```shell
./bin/rq worker normal low --with-scheduler
```

`--with-scheduler` is needed in order to retry failed jobs after a certain time period.

Or yous the `worker` command
```shell
make worker
```

6. Go to the control panel and repeat the following stepts.

- Check "Enable"
- Click "Convert Catalog"
- Click "Rebuild Catalog"

### Technical documentation for elasticsearch

#### Pipeline

If you hit convert in the control panel and you meet all the requirements to index blobs as well,
collective.elasticsearch installs a default pipeline for the plone-index.
This Pipeline coverts the binary data to text (if possible) and extends the searchableText index with the extracted data
The setup uses multiple nested processors in order to extract all binary data from all fields (blob fields).

The binary data is not stored in index permanently. As last step the pipeline removes the binary itself.

#### ingest-attachment plugin

The ingest-attachment plugin is used to extract text data with tika from any binary.


### Note on Performance

Putting all the jobs into a queue is much faster then actually calculate all index values and send them to elasticsearch.
This feature aims to have a minimal impact in terms of responsiveness of the plone site.


## Compatibility

- Python 3
- Plone 5.2 and above
- Tested with Elastic Search 7.17.0

## State

Support for all index column types is done EXCEPT for the DateRecurringIndex index column type. If you are doing a full text search along with a query that contains a DateRecurringIndex column, it will not work.


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
