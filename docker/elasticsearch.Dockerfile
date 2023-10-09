FROM elasticsearch:8.10.2

RUN bin/elasticsearch-plugin install ingest-attachment -b
