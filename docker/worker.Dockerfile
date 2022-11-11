FROM plone/plone-backend:6.0.0b3

WORKDIR /app

RUN /app/bin/pip install git+https://github.com/collective/collective.elasticsearch.git@mle-redis-rq#egg=collective.elasticsearch[redis]

CMD /app/bin/rq worker normal low --with-scheduler --url=$PLONE_REDIS_DSN
