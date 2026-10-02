from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

QUERY_TOTAL = Counter(
    "collection_agent_queries_total",
    "Total customer queries received",
    ["intent", "status"]
)

RETRIEVAL_LATENCY = Histogram(
    "collection_agent_retrieval_seconds",
    "Time spent in hybrid search and reranking",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

LLM_LATENCY = Histogram(
    "collection_agent_llm_seconds",
    "Time spent in LLM synthesis",
    buckets=[0.2, 0.5, 1.0, 2.0, 4.0, 8.0]
)

TOOL_EXECUTION_TOTAL = Counter(
    "collection_agent_tool_executions_total",
    "Count of tool executions",
    ["tool_name", "status"]
)

CALL_DISPOSITIONS_TOTAL = Counter(
    "collection_agent_dispositions_total",
    "Count of completed call dispositions",
    ["outcome"]
)


def get_prometheus_metrics() -> tuple[bytes, str]:
    """Generates the Prometheus metrics payload and content type."""
    return generate_latest(), CONTENT_TYPE_LATEST
