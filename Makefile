### Defensive settings for make:
#     https://tech.davis-hansson.com/p/make/
SHELL:=bash
.ONESHELL:
.SHELLFLAGS:=-xeu -o pipefail -O inherit_errexit -c
.SILENT:
.DELETE_ON_ERROR:
MAKEFLAGS+=--warn-undefined-variables
MAKEFLAGS+=--no-builtin-rules

# We like colors
# From: https://coderwall.com/p/izxssa/colored-makefile-for-golang-projects
RED=`tput setaf 1`
GREEN=`tput setaf 2`
RESET=`tput sgr0`
YELLOW=`tput setaf 3`

PLONE5=5.2-latest
PLONE6=6.0-latest

INSTANCE_YAML=instance.yaml

ELASTIC_SEARCH_IMAGE=elasticsearch:7.17.7
ELASTIC_SEARCH_CONTAINER=elastictest

REDIS_IMAGE=redis:7.0.5
REDIS_CONTAINER=redistest

ELASTIC_SEARCH_CONTAINERS=$$(docker ps -q -a -f "name=${ELASTIC_SEARCH_CONTAINER}" | wc -l)
REDIS_CONTAINERS=$$(docker ps -q -a -f "name=${REDIS_CONTAINER}" | wc -l)

# Default env for elasticsearch with redis queue
DEFAULT_ENV_ES_REDIS=PLONE_REDIS_DSN=redis://localhost:6379/0 \
	PLONE_BACKEND=http://localhost:8080/Plone \
	PLONE_USERNAME=admin \
	PLONE_PASSWORD=admin

ifndef LOG_LEVEL
	LOG_LEVEL=INFO
endif

CODE_QUALITY_VERSION=2.0.0
CURRENT_USER=$$(whoami)
USER_INFO=$$(id -u ${CURRENT_USER}):$$(getent group ${CURRENT_USER}|cut -d: -f3)
BASE_FOLDER=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
LINT=docker run -e LOG_LEVEL="${LOG_LEVEL}" --rm -v "${BASE_FOLDER}":/github/workspace plone/code-quality:${CODE_QUALITY_VERSION} check
FORMAT=docker run --user="${USER_INFO}" -e LOG_LEVEL="${LOG_LEVEL}" --rm -v "${BASE_FOLDER}":/github/workspace plone/code-quality:${CODE_QUALITY_VERSION} format

all: build

# Add the following 'help' target to your Makefile
# And add help text after each target name starting with '\#\#'
.PHONY: help
help: ## This help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

bin/pip:
	@echo "$(GREEN)==> Setup Virtual Env$(RESET)"
	python3 -m venv .
	bin/pip install -U pip wheel

.PHONY: cookiecutter
cookiecutter: bin/pip
	@echo "$(GREEN)Install cookiecutter$(RESET)"
	bin/pip install git+https://github.com/cookiecutter/cookiecutter.git#egg=cookiecutter

.PHONY: instance
instance: cookiecutter ## create configuration for an zope (plone) instance
	@echo "$(GREEN)Create Plone/Zope configuration$(RESET)"
	rm -fr ./etc
	bin/cookiecutter -f --no-input --config-file ${INSTANCE_YAML} https://github.com/bluedynamics/cookiecutter-zope-instance

.PHONY: build-plone-5
build-plone-5: bin/pip ## Build Plone 5.2
	@echo "$(GREEN)==> Build with Plone 5.2$(RESET)"
	bin/pip install Paste Plone -c https://dist.plone.org/release/$(PLONE5)/constraints.txt
	bin/pip install "zest.releaser[recommended]"
	bin/pip install -e ".[test, redis]"
	make instance

.PHONY: build-plone-6
build-plone-6: bin/pip ## Build Plone 6.0
	@echo "$(GREEN)==> Build with Plone 6.0$(RESET)"
	bin/pip install Plone -c https://dist.plone.org/release/$(PLONE6)/constraints.txt
	bin/pip install "zest.releaser[recommended]"
	bin/pip install -e ".[test, redis]"
	make instance

.PHONY: build
build: build-plone-6 ## Build Plone 6.0

.PHONY: clean
clean: ## Remove old virtualenv and creates a new one
	@echo "$(RED)==> Cleaning environment and build$(RESET)"
	rm -rf bin lib lib64 include share etc var inituser pyvenv.cfg .installed.cfg

.PHONY: format
format: ## Format the codebase according to our standards
	@echo "$(GREEN)==> Format codebase$(RESET)"
	$(FORMAT)

.PHONY: format-black
format-black:  ## Format the codebase with black
	@echo "$(GREEN)==> Format codebase with black$(RESET)"
	$(FORMAT) black ${CODEPATH}

.PHONY: format-isort
format-isort:  ## Format the codebase with isort
	@echo "$(GREEN)==> Format codebase with isort$(RESET)"
	$(FORMAT) isort ${CODEPATH}

.PHONY: format-zpretty
format-zpretty:  ## Format the codebase with zpretty
	@echo "$(GREEN)==> Format codebase with zpretty$(RESET)"
	$(FORMAT) zpretty ${CODEPATH}

.PHONY: lint
lint: ## check code style
	$(LINT)

.PHONY: lint-black
lint-black: ## validate black formating
	$(LINT) black ${CODEPATH}

.PHONY: lint-flake8
lint-flake8: ## validate black formating
	$(LINT) flake8 ${CODEPATH}

.PHONY: lint-isort
lint-isort: ## validate using isort
	$(LINT) isort ${CODEPATH}

.PHONY: lint-pyroma
lint-pyroma: ## validate using pyroma
	$(LINT) pyroma ${CODEPATH}

.PHONY: lint-zpretty
lint-zpretty: ## validate ZCML/XML using zpretty
	$(LINT) zpretty ${CODEPATH}

.PHONY: elastic
elastic: ## Create Elastic Search container
	@if [ $(ELASTIC_SEARCH_CONTAINERS) -eq 0 ]; then \
		docker container create --name $(ELASTIC_SEARCH_CONTAINER) \
		-e "discovery.type=single-node" \
		-e "cluster.name=docker-cluster" \
		-e "http.cors.enabled=true" \
		-e "http.cors.allow-origin=*" \
		-e "http.cors.allow-headers=X-Requested-With,X-Auth-Token,Content-Type,Content-Length,Authorization" \
		-e "http.cors.allow-credentials=true" \
		-e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
		-p 9200:9200 \
		-p 9300:9300 \
		$(ELASTIC_SEARCH_IMAGE); \
		docker start $(ELASTIC_SEARCH_CONTAINER); \
		docker exec $(ELASTIC_SEARCH_CONTAINER) /bin/sh -c "bin/elasticsearch-plugin install ingest-attachment -b"; \
		docker stop $(ELASTIC_SEARCH_CONTAINER);fi

.PHONY: start-elastic
start-elastic: elastic ## Start Elastic Search
	@echo "$(GREEN)==> Start Elastic Search$(RESET)"
	@docker start $(ELASTIC_SEARCH_CONTAINER)

.PHONY: stop-elastic
stop-elastic: ## Stop Elastic Search
	@echo "$(GREEN)==> Stop Elastic Search$(RESET)"
	@docker stop $(ELASTIC_SEARCH_CONTAINER)

.PHONY: redis
redis: ## Create redis Search container
	@if [ $(REDIS_CONTAINERS) -eq 0 ]; then \
		docker container create --name $(REDIS_CONTAINER) \
		-p 6379:6379 \
		$(REDIS_IMAGE);fi


.PHONY: start-redis
start-redis: redis ## Start redis
	@echo "$(GREEN)==> Start redis$(RESET)"
	@docker start $(REDIS_CONTAINER)

.PHONY: stop-redis
stop-redis: ## Stop redis
	@echo "$(GREEN)==> Stop redis$(RESET)"
	@docker stop $(REDIS_CONTAINER)


.PHONY: test
test: ## run tests
	make start-elastic
	make start-redis
	PYTHONWARNINGS=ignore ./bin/zope-testrunner --auto-color --auto-progress --test-path src/
	make stop-elastic
	make stop-redis

.PHONY: start
start: ## Start a Plone instance on localhost:8080
	PYTHONWARNINGS=ignore ./bin/runwsgi instance/etc/zope.ini

.PHONY: populate
populate: ## Populate site with wikipedia content
	PYTHONWARNINGS=ignore ./bin/zconsole run etc/zope.conf scripts/populate.py

.PHONY: start-redis-support
start-redis-support: ## Start a Plone instance on localhost:8080
	@echo "$(GREEN)==> Set env variables, PLONE_REDIS_DSN, PLONE_BACKEND, PLONE_USERNAME and PLONE_PASSWORD before start instance$(RESET)"
	PYTHONWARNINGS=ignore \
	$(DEFAULT_ENV_ES_REDIS) \
	./bin/runwsgi instance/etc/zope.ini


.PHONY: worker
worker: ## Start a worker for the redis queue
	$(DEFAULT_ENV_ES_REDIS) ./bin/rq worker normal low --with-scheduler
