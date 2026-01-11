FROM postgres:16

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-cron \
    openssl \
    dos2unix \
 && rm -rf /var/lib/apt/lists/*

COPY init-ssl.sh /docker-entrypoint-initdb.d/01-init-ssl.sh
RUN dos2unix /docker-entrypoint-initdb.d/01-init-ssl.sh \
 && chmod 755 /docker-entrypoint-initdb.d/01-init-ssl.sh

COPY init-user.sh /docker-entrypoint-initdb.d/02-init-user.sh
RUN dos2unix /docker-entrypoint-initdb.d/02-init-user.sh \
 && chmod 755 /docker-entrypoint-initdb.d/02-init-user.sh
