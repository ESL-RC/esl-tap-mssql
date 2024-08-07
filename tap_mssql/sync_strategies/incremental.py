#!/usr/bin/env python3
# pylint: disable=duplicate-code

'''
    Highly Customized by Roger
    - To sync the replication_key_value - 10 days before due to Poor DB design

'''

import pendulum
import singer
from singer import metadata

import tap_mssql.sync_strategies.common as common
from tap_mssql.connection import MSSQLConnection, connect_with_backoff

LOGGER = singer.get_logger()

BOOKMARK_KEYS = {"replication_key", "replication_key_value", "version"}


def sync_table(mssql_conn, config, catalog_entry, state, columns):
    mssql_conn = MSSQLConnection(config)
    common.whitelist_bookmark_keys(BOOKMARK_KEYS, catalog_entry.tap_stream_id, state)

    catalog_metadata = metadata.to_map(catalog_entry.metadata)
    stream_metadata = catalog_metadata.get((), {})

    # Adding 1 more key to sync
    replication_key_2 = stream_metadata.get("replication-key-2")

    # Adding another key to sync
    replication_key_3 = stream_metadata.get("replication-key-3")


    replication_key_metadata = stream_metadata.get("replication-key")
    replication_key_state = singer.get_bookmark(
        state, catalog_entry.tap_stream_id, "replication_key"
    )

    replication_key_value = None

    if replication_key_metadata == replication_key_state:
        replication_key_value = singer.get_bookmark(
            state, catalog_entry.tap_stream_id, "replication_key_value"
        )
    else:
        state = singer.write_bookmark(
            state, catalog_entry.tap_stream_id, "replication_key", replication_key_metadata
        )
        state = singer.clear_bookmark(state, catalog_entry.tap_stream_id, "replication_key_value")

    stream_version = common.get_stream_version(catalog_entry.tap_stream_id, state)
    state = singer.write_bookmark(state, catalog_entry.tap_stream_id, "version", stream_version)

    activate_version_message = singer.ActivateVersionMessage(
        stream=catalog_entry.stream, version=stream_version
    )

    singer.write_message(activate_version_message)
    LOGGER.info("Beginning SQL")
    with connect_with_backoff(mssql_conn) as open_conn:
        with open_conn.cursor() as cur:
            select_sql = common.generate_select_sql(catalog_entry, columns)
            params = {}

            if replication_key_value is not None:
                if catalog_entry.schema.properties[replication_key_metadata].format == "date-time":
                    replication_key_value = pendulum.parse(replication_key_value).subtract(days=10).format('YYYY-MM-DDTHH:MM:ss.SSS') 

                select_sql += ' WHERE "{}" >= %(replication_key_value)s'.format(
                    replication_key_metadata
                )

                if replication_key_2:
                    select_sql += ' OR "{}" >= %(replication_key_value)s'.format(
                        replication_key_2
                    )

                if replication_key_3:
                    select_sql += ' OR "{}" >= %(replication_key_value)s'.format(
                        replication_key_3
                    )

                select_sql += ' ORDER BY "{}" ASC'.format(
                    replication_key_metadata
                )

                params["replication_key_value"] = replication_key_value
            elif replication_key_metadata is not None:
                select_sql += ' ORDER BY "{}" ASC'.format(replication_key_metadata)

            common.sync_query(
                cur, catalog_entry, state, select_sql, columns, stream_version, params, config
            )
