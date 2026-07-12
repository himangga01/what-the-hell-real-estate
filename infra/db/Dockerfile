# syntax=docker/dockerfile:1

# PostgreSQL 18 + PostGIS 3.6 is maintained by the PostGIS project.
FROM postgis/postgis:18-3.6

ARG PGVECTOR_VERSION=0.8.2

LABEL org.opencontainers.image.title="What The Hell Real Estate local database" \
      org.opencontainers.image.description="PostgreSQL 18 with PostGIS 3.6 and pgvector 0.8.2" \
      org.opencontainers.image.source="https://github.com/pgvector/pgvector" \
      org.opencontainers.image.version="postgres18-postgis3.6-pgvector0.8.2"

# Match pgvector's official source-build installation while retaining PostGIS.
# The Git reference is deliberately literal so overriding a build argument cannot
# silently fetch a different source revision.
ADD https://github.com/pgvector/pgvector.git#v0.8.2 /tmp/pgvector

RUN set -eux; \
    test "${PG_MAJOR}" = "18"; \
    case "${POSTGIS_VERSION}" in \
        3.6*) ;; \
        *) echo >&2 "Expected PostGIS 3.6.x, found ${POSTGIS_VERSION}"; exit 1 ;; \
    esac; \
    test "${PGVECTOR_VERSION}" = "0.8.2"; \
    apt-get update; \
    apt-mark hold locales; \
    apt-get install -y --no-install-recommends \
        build-essential \
        "postgresql-server-dev-${PG_MAJOR}"; \
    cd /tmp/pgvector; \
    make clean; \
    make OPTFLAGS=""; \
    make install; \
    install -d /usr/share/doc/pgvector; \
    install -m 0644 LICENSE README.md /usr/share/doc/pgvector/; \
    grep -Fqx "default_version = '0.8.2'" \
        "/usr/share/postgresql/${PG_MAJOR}/extension/vector.control"; \
    rm -rf /tmp/pgvector; \
    apt-get remove -y build-essential "postgresql-server-dev-${PG_MAJOR}"; \
    apt-get autoremove -y; \
    apt-mark unhold locales; \
    rm -rf /var/lib/apt/lists/*
