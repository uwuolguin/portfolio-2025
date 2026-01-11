FROM postgres:16

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-cron \
    openssl \
    dos2unix \
 && rm -rf /var/lib/apt/lists/*

COPY init-ssl.sh /docker-entrypoint-initdb.d/01-init-ssl.sh
RUN dos2unix /docker-entrypoint-initdb.d/01-init-ssl.sh \
 && chmod 755 /docker-entrypoint-initdb.d/01-init-ssl.sh

COPY init-db.sh /docker-entrypoint-initdb.d/02-init-db.sh
RUN dos2unix /docker-entrypoint-initdb.d/02-init-db.sh \
 && chmod 755 /docker-entrypoint-initdb.d/02-init-db.sh

COPY init-pgpass.sh /docker-entrypoint-initdb.d/03-init-pgpass.sh
RUN dos2unix /docker-entrypoint-initdb.d/03-init-pgpass.sh \
 && chmod 755 /docker-entrypoint-initdb.d/03-init-pgpass.sh