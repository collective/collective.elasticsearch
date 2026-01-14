"""
Compatibility layer for Elasticsearch 7.x and 8.x Python client.

This module provides helper functions to handle API differences between
elasticsearch-py versions 7.x and 8.x.
"""
from elasticsearch import VERSION as ES_VERSION


ES_MAJOR_VERSION = ES_VERSION[0]
IS_ES_8 = ES_MAJOR_VERSION >= 8


def normalize_hosts(hosts):
    """
    Normalize hosts for ES client compatibility.

    In ES 8, hosts must include a scheme (http:// or https://).
    In ES 7, hosts can be just hostname or hostname:port.

    Args:
        hosts: List of host strings.

    Returns:
        List of normalized host strings.
    """
    if not IS_ES_8:
        return hosts

    normalized = []
    for host in hosts:
        if not host.startswith(("http://", "https://")):
            # Default to http if no scheme provided
            if ":" in host:
                # Has port already
                normalized.append(f"http://{host}")
            else:
                # Add default ES port
                normalized.append(f"http://{host}:9200")
        else:
            normalized.append(host)
    return normalized


def get_connection_params(settings):
    """
    Build connection parameters compatible with the installed ES client version.

    Args:
        settings: IElasticSettings registry record with connection configuration.

    Returns:
        Dictionary of connection parameters suitable for Elasticsearch() init.
    """
    if IS_ES_8:
        params = {
            "retry_on_timeout": settings.retry_on_timeout,
            "request_timeout": settings.timeout,
        }
        # Only enable sniffing if explicitly configured
        # In ES 8, sniffing can cause connection issues in Docker/test environments
        if settings.sniff_on_start:
            params["sniff_on_start"] = True
        if settings.sniff_on_connection_fail:
            params["sniff_on_node_failure"] = True
        if settings.sniffer_timeout and settings.sniffer_timeout > 0:
            params["min_delay_between_sniffing"] = settings.sniffer_timeout
        return params
    return {
        "retry_on_timeout": settings.retry_on_timeout,
        "sniff_on_connection_fail": settings.sniff_on_connection_fail,
        "sniff_on_start": settings.sniff_on_start,
        "sniffer_timeout": settings.sniffer_timeout,
        "timeout": settings.timeout,
    }


def es_search(conn, index, body, **kwargs):
    """
    Execute a search query compatible with both ES 7 and ES 8.

    Args:
        conn: Elasticsearch client connection.
        index: Index name to search.
        body: Query body dictionary.
        **kwargs: Additional search parameters.

    Returns:
        Search response (dict-like object).
    """
    if IS_ES_8:
        return conn.search(index=index, **body, **kwargs)
    return conn.search(index=index, body=body, **kwargs)


def es_bulk(conn, index, body):
    """
    Execute bulk operations compatible with both ES 7 and ES 8.

    Args:
        conn: Elasticsearch client connection.
        index: Index name for bulk operations.
        body: List of bulk operation actions.

    Returns:
        Bulk response dictionary.
    """
    if IS_ES_8:
        return conn.bulk(index=index, operations=body)
    return conn.bulk(index=index, body=body)


def indices_create(conn, index, body=None):
    """
    Create an index compatible with both ES 7 and ES 8.

    Args:
        conn: Elasticsearch client connection.
        index: Index name to create.
        body: Index creation body with settings/mappings.

    Returns:
        Index creation response.
    """
    if body is None:
        body = {}
    if IS_ES_8:
        return conn.indices.create(index=index, **body)
    return conn.indices.create(index=index, body=body)


def indices_put_mapping(conn, index, body):
    """
    Update index mapping compatible with both ES 7 and ES 8.

    Args:
        conn: Elasticsearch client connection.
        index: Index name to update.
        body: Mapping body dictionary.

    Returns:
        Put mapping response.
    """
    if IS_ES_8:
        return conn.indices.put_mapping(index=index, **body)
    return conn.indices.put_mapping(index=index, body=body)


def indices_put_settings(conn, index, body):
    """
    Update index settings compatible with both ES 7 and ES 8.

    Args:
        conn: Elasticsearch client connection.
        index: Index name to update.
        body: Settings body dictionary.

    Returns:
        Put settings response.
    """
    if IS_ES_8:
        # In ES 8, put_settings accepts 'settings' parameter, not unpacked body
        return conn.indices.put_settings(index=index, settings=body)
    return conn.indices.put_settings(index=index, body=body)


def ingest_put_pipeline(conn, pipeline_id, body):
    """
    Create or update an ingest pipeline compatible with both ES 7 and ES 8.

    Args:
        conn: Elasticsearch client connection.
        pipeline_id: Pipeline identifier.
        body: Pipeline definition body.

    Returns:
        Put pipeline response.
    """
    if IS_ES_8:
        return conn.ingest.put_pipeline(id=pipeline_id, **body)
    return conn.ingest.put_pipeline(id=pipeline_id, body=body)


def es_update(conn, index, doc_id, body, **kwargs):
    """
    Update a document compatible with both ES 7 and ES 8.

    Args:
        conn: Elasticsearch client connection.
        index: Index name.
        doc_id: Document ID.
        body: Update body - either a dict with 'doc' key or raw bytes (e.g., cbor).
        **kwargs: Additional parameters like headers.

    Returns:
        Update response.
    """
    if IS_ES_8:
        # In ES 8, for raw body content (bytes like CBOR), use node directly
        # The ES 8 client doesn't support application/cbor content type
        if isinstance(body, bytes):
            node = conn.transport.node_pool.get()
            return node.perform_request(
                "POST",
                f"/{index}/_update/{doc_id}",
                body=body,
                headers=kwargs.get("headers", {}),
            )
        # For dict bodies, unpack the body into keyword arguments
        return conn.update(index=index, id=doc_id, **body, **kwargs)
    return conn.update(index=index, id=doc_id, body=body, **kwargs)


def has_attachment_processor(conn):
    """
    Check if the attachment processor is available.

    In ES 7, ingest-attachment is a plugin (check via cat.plugins()).
    In ES 8, ingest-attachment is a built-in module (check via _nodes/ingest).

    Args:
        conn: Elasticsearch client connection.

    Returns:
        True if attachment processor is available, False otherwise.
    """
    if IS_ES_8:
        try:
            nodes_info = conn.nodes.info(metric="ingest")
            for node_id, node_data in nodes_info.get("nodes", {}).items():
                processors = node_data.get("ingest", {}).get("processors", [])
                for processor in processors:
                    if processor.get("type") == "attachment":
                        return True
            return False
        except Exception:
            return False
    else:
        return "attachment" in conn.cat.plugins()


def scan_search(conn, index, query):
    """
    Prepare scan/scroll search parameters compatible with both ES 7 and ES 8.

    In ES 8, the scan helper no longer accepts a full body with 'query' key,
    instead it expects the query directly.

    Args:
        conn: Elasticsearch client connection.
        index: Index name to search.
        query: Query dictionary (full body with 'query' and '_source' keys).

    Returns:
        Dictionary of kwargs to pass to elasticsearch.helpers.scan()
    """
    if IS_ES_8:
        return {
            "client": conn,
            "index": index,
            "query": query.get("query"),
            "_source": query.get("_source"),
        }
    return {
        "client": conn,
        "index": index,
        "query": query,
    }
