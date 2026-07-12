\set ON_ERROR_STOP on

-- Fail early when this script is accidentally run against another PostgreSQL major.
DO $validation$
BEGIN
    IF current_setting('server_version_num')::integer / 10000 <> 18 THEN
        RAISE EXCEPTION
            'Unsupported PostgreSQL version: %. PostgreSQL 18.x is required.',
            current_setting('server_version');
    END IF;
END
$validation$;

-- Both statements are safe to run repeatedly in an already initialized database.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

DO $validation$
DECLARE
    installed_postgis_version text;
    installed_vector_version text;
BEGIN
    SELECT extversion
      INTO STRICT installed_postgis_version
      FROM pg_catalog.pg_extension
     WHERE extname = 'postgis';

    IF installed_postgis_version !~ '^3\.6(\.|$)' THEN
        RAISE EXCEPTION
            'Unsupported PostGIS version: %. PostGIS 3.6.x is required.',
            installed_postgis_version;
    END IF;

    SELECT extversion
      INTO STRICT installed_vector_version
      FROM pg_catalog.pg_extension
     WHERE extname = 'vector';

    IF installed_vector_version <> '0.8.2' THEN
        RAISE EXCEPTION
            'Unsupported pgvector version: %. pgvector 0.8.2 is required.',
            installed_vector_version;
    END IF;
END
$validation$;
