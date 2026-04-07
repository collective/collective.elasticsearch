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
PLONE6=6.2-latest

INSTANCE_YAML=instance.yaml

# Elasticsearch configuration
ELASTIC_SEARCH_7_IMAGE=elasticsearch:7.17.7
ELASTIC_SEARCH_8_IMAGE=elasticsearch:8.17.0
ELASTIC_SEARCH_7_CONTAINER=elastictest_7
ELASTIC_SEARCH_8_CONTAINER=elastictest_8

REDIS_IMAGE=redis:7.0.5
REDIS_CONTAINER=redistest

ELASTIC_SEARCH_7_CONTAINERS=$$(docker ps -q -a -f "name=^${ELASTIC_SEARCH_7_CONTAINER}$$" | wc -l | tr -d ' ')
ELASTIC_SEARCH_8_CONTAINERS=$$(docker ps -q -a -f "name=^${ELASTIC_SEARCH_8_CONTAINER}$$" | wc -l | tr -d ' ')
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
build-plone-6: bin/pip ## Build Plone 6.2
	@echo "$(GREEN)==> Build with Plone 6.2$(RESET)"
	bin/pip install Plone -c https://dist.plone.org/release/$(PLONE6)/constraints.txt
	bin/pip install "zest.releaser[recommended]"
	bin/pip install -e ".[test, redis]"
	make instance

.PHONY: build
build: build-plone-6 ## Build Plone 6.2

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

# Elasticsearch 7 container management
.PHONY: elastic-7
elastic-7: ## Create Elasticsearch 7 container
	@if [ $(ELASTIC_SEARCH_7_CONTAINERS) -eq 0 ]; then \
		echo "$(GREEN)==> Creating Elasticsearch 7 container$(RESET)"; \
		docker container create --name $(ELASTIC_SEARCH_7_CONTAINER) \
		-e "discovery.type=single-node" \
		-e "cluster.name=docker-cluster" \
		-e "http.cors.enabled=true" \
		-e "http.cors.allow-origin=*" \
		-e "http.cors.allow-headers=X-Requested-With,X-Auth-Token,Content-Type,Content-Length,Authorization" \
		-e "http.cors.allow-credentials=true" \
		-e "xpack.security.enabled=false" \
		-e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
		-p 9200:9200 \
		-p 9300:9300 \
		$(ELASTIC_SEARCH_7_IMAGE); \
		docker start $(ELASTIC_SEARCH_7_CONTAINER); \
		docker exec $(ELASTIC_SEARCH_7_CONTAINER) /bin/sh -c "bin/elasticsearch-plugin install ingest-attachment -b"; \
		docker stop $(ELASTIC_SEARCH_7_CONTAINER); \
	fi

# Elasticsearch 8 container management
.PHONY: elastic-8
elastic-8: ## Create Elasticsearch 8 container
	@if [ $(ELASTIC_SEARCH_8_CONTAINERS) -eq 0 ]; then \
		echo "$(GREEN)==> Creating Elasticsearch 8 container$(RESET)"; \
		docker container create --name $(ELASTIC_SEARCH_8_CONTAINER) \
		-e "discovery.type=single-node" \
		-e "cluster.name=docker-cluster" \
		-e "xpack.security.enabled=false" \
		-e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
		-p 9200:9200 \
		-p 9300:9300 \
		$(ELASTIC_SEARCH_8_IMAGE); \
		docker start $(ELASTIC_SEARCH_8_CONTAINER); \
		docker stop $(ELASTIC_SEARCH_8_CONTAINER); \
	fi

.PHONY: start-elastic-7
start-elastic-7: elastic-7 ## Start Elasticsearch 7
	@echo "$(GREEN)==> Start Elasticsearch 7$(RESET)"
	@docker start $(ELASTIC_SEARCH_7_CONTAINER)
	@sleep 10

.PHONY: stop-elastic-7
stop-elastic-7: ## Stop Elasticsearch 7
	@echo "$(GREEN)==> Stop Elasticsearch 7$(RESET)"
	@docker stop $(ELASTIC_SEARCH_7_CONTAINER) 2>/dev/null || true

.PHONY: start-elastic-8
start-elastic-8: elastic-8 ## Start Elasticsearch 8
	@echo "$(GREEN)==> Start Elasticsearch 8$(RESET)"
	@docker start $(ELASTIC_SEARCH_8_CONTAINER)
	@sleep 10

.PHONY: stop-elastic-8
stop-elastic-8: ## Stop Elasticsearch 8
	@echo "$(GREEN)==> Stop Elasticsearch 8$(RESET)"
	@docker stop $(ELASTIC_SEARCH_8_CONTAINER) 2>/dev/null || true

.PHONY: remove-elastic-7
remove-elastic-7: ## Remove Elasticsearch 7 container
	@docker rm -f $(ELASTIC_SEARCH_7_CONTAINER) 2>/dev/null || true

.PHONY: remove-elastic-8
remove-elastic-8: ## Remove Elasticsearch 8 container
	@docker rm -f $(ELASTIC_SEARCH_8_CONTAINER) 2>/dev/null || true

.PHONY: redis
redis: ## Create redis container
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
	@docker stop $(REDIS_CONTAINER) 2>/dev/null || true

# Test targets
.PHONY: test
test: test-es7 test-es8 ## Run tests against ES 7 and ES 8

.PHONY: test-es7
test-es7: ## Run tests with Elasticsearch 7
	@echo "$(GREEN)==> Running tests with Elasticsearch 7$(RESET)"
	@make stop-elastic-8 2>/dev/null || true
	@make start-elastic-7
	@make start-redis
	./bin/pip install "elasticsearch>=7.17.0,<8.0.0" --quiet
	PYTHONWARNINGS=ignore ./bin/zope-testrunner --auto-color --auto-progress --test-path src/
	@make stop-elastic-7
	@make stop-redis

.PHONY: test-es8
test-es8: ## Run tests with Elasticsearch 8
	@echo "$(GREEN)==> Running tests with Elasticsearch 8$(RESET)"
	@make stop-elastic-7 2>/dev/null || true
	@make start-elastic-8
	@make start-redis
	./bin/pip install "elasticsearch>=8.0.0,<9.0.0" --quiet
	PYTHONWARNINGS=ignore ./bin/zope-testrunner --auto-color --auto-progress --test-path src/
	@make stop-elastic-8
	@make stop-redis

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
