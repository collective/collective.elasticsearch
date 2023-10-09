FROM plone/plone-backend:6.0.7

WORKDIR /app

RUN /app/bin/pip install git+https://github.com/collective/collective.elasticsearch.git@main#egg=collective.elasticsearch[redis]

ENV PROFILES="collective.elasticsearch:default collective.elasticsearch:docker-dev"
ENV TYPE="classic"
ENV SITE="Plone"
