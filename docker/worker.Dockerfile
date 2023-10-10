FROM plone/plone-backend:6.0.7

WORKDIR /app

RUN /app/bin/pip install git+https://github.com/collective/collective.elasticsearch.git@main#egg=collective.elasticsearch[redis]

CMD /app/bin/rq worker normal low --with-scheduler --url=$PLONE_REDIS_DSN
