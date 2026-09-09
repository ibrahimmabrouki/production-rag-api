"""
This File is supposed to test the Settings Pydantic-Settings class
use the following command to run the test:
python -m tests.test_settings  

"""

from app.core.config import get_settings


def settings_test():
    settings = get_settings()

    print("\n========== APPLICATION SETTINGS ==========")
    print(f"Environment: {settings.app_env}")
    print(f"Production: {settings.is_production}")
    print(f"Log Level: {settings.log_level}")
    print(f"Rate Limit: {settings.rate_limit}")
    print(f"Cache TTL: {settings.cache_ttl_seconds} seconds")
    print(f"Max Retries: {settings.max_retries}")

    # LLM
    print("\n========== LLM SETTINGS ==========")
    print(f"Gemini API Key configured: {bool(settings.gemini_api_key)}")
    print(f"Primary Model: {settings.primary_model}")
    print(f"Fallback Model: {settings.fallback_model}")

    # LangSmith
    print("\n========== LANGSMITH SETTINGS ==========")
    print(f"LangChain Tracing: {settings.langchain_tracing_v2}")
    print(f"LangChain API Key configured: {bool(settings.langchain_api_key)}")
    print(f"LangChain Project: {settings.langchain_project}")

    # Token Budget
    print("\n========== TOKEN BUDGET SETTINGS ==========")
    print(f"Max Input Tokens: {settings.token_max_input}")
    print(f"Max Tokens Per Chat: {settings.token_max_chat}")
    print(
        f"Max Requests Per Chat: "
        f"{settings.token_max_requests_per_chat}"
    )

    # Redis
    print("\n========== REDIS SETTINGS ==========")
    print(f"Redis URL: {settings.redis_url}")
    print(f"Redis Max Connections: {settings.redis_max_connections}")
    print(f"Redis Socket Timeout: {settings.redis_socket_timeout} seconds")
    print(
        f"Redis Socket Connect Timeout: "
        f"{settings.redis_socket_connect_timeout} seconds"
    )
    print(
        f"Redis Health Check Interval: "
        f"{settings.redis_health_check_interval} seconds"
    )

    # Embedding / Semantic Cache
    print("\n========== EMBEDDING SETTINGS ==========")
    print(f"Embedding Model: {settings.embedding_model}")
    print(f"Embedding Dimension: {settings.embedding_dimension}")
    print(
        f"Semantic Cache Similarity Threshold: "
        f"{settings.semantic_cache_similarity_threshold}"
    )
    print(f"Semantic Cache Top K: {settings.semantic_cache_top_k}")

    # Grafana / Monitoring
    print("\n========== MONITORING SETTINGS ==========")
    print(f"Monitoring Enabled: {settings.monitoring_enabled}")
    print(
        f"Grafana OTLP Endpoint Configured: "
        f"{bool(settings.grafana_otlp_endpoint)}"
    )
    print(
        f"Grafana Instance ID Configured: "
        f"{bool(settings.grafana_instance_id)}"
    )
    print(
        f"Grafana API Key Configured: "
        f"{bool(settings.grafana_api_key)}"
    )

    print("\n==========================================")


if __name__ == "__main__":
    settings_test()
