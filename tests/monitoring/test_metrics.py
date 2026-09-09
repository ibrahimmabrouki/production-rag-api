"""
This file is supposed to test the Metrics Collector functionality.

Use the following command to run the test:
python -m tests.monitoring.test_metrics
"""

import time

from prometheus_client import generate_latest

from app.core.monitoring.metrics import (
    metrics,
    SECURITY_CHECKS_TOTAL,
    REQUESTS_TOTAL,
    REQUEST_ERRORS_TOTAL,
    REQUEST_LATENCY,
    LLM_REQUESTS_TOTAL,
    LLM_ERRORS_TOTAL,
    LLM_LATENCY,
    LLM_INPUT_TOKENS_TOTAL,
    LLM_OUTPUT_TOKENS_TOTAL,
    TOKEN_LIMIT_EXCEEDED_TOTAL,
    CACHE_REQUESTS_TOTAL,
    CACHE_ERRORS_TOTAL,
    CACHE_LATENCY,
    RAG_REQUESTS_TOTAL,
    RAG_ERRORS_TOTAL,
    RAG_LATENCY,
    ACTIVE_REQUESTS,
)


# ============================================================
# Test 1: Record input security allowed
# ============================================================

print("\n--- Test 1: Input Security Allowed ---")

metrics.record_security_check(
    stage="input",
    result="allowed",
)

security_allowed = SECURITY_CHECKS_TOTAL.labels(
    stage="input",
    result="allowed",
)._value.get()

print(f"Input security allowed: {security_allowed}")


# ============================================================
# Test 2: Record output security blocked
# ============================================================

print("\n--- Test 2: Output Security Blocked ---")

metrics.record_security_check(
    stage="output",
    result="blocked",
)

security_blocked = SECURITY_CHECKS_TOTAL.labels(
    stage="output",
    result="blocked",
)._value.get()

print(f"Output security blocked: {security_blocked}")


# ============================================================
# Test 3: Record a basic API request
# ============================================================

print("\n--- Test 3: API Request ---")

metrics.record_request(
    method="POST",
    endpoint="/chat",
    status=200,
)

request_count = REQUESTS_TOTAL.labels(
    method="POST",
    endpoint="/chat",
    status="200",
)._value.get()

print(f"API requests recorded: {request_count}")


# ============================================================
# Test 4: Record an API error
# ============================================================

print("\n--- Test 4: API Error ---")

metrics.record_request_error(
    endpoint="/chat",
    error_type="ValidationError",
)

error_count = REQUEST_ERRORS_TOTAL.labels(
    endpoint="/chat",
    error_type="ValidationError",
)._value.get()

print(f"API errors recorded: {error_count}")


# ============================================================
# Test 5: Track API request latency
# ============================================================

print("\n--- Test 5: API Request Latency ---")

with metrics.track_request_latency(
    method="POST",
    endpoint="/chat",
):
    time.sleep(0.5)

api_latency = REQUEST_LATENCY.labels(
    method="POST",
    endpoint="/chat",
)

print(
    f"API latency total: "
    f"{api_latency._sum.get():.4f} seconds"
)


# ============================================================
# Test 6: Record an LLM request
# ============================================================

print("\n--- Test 6: LLM Request ---")

metrics.record_llm_request(
    model="gemini-3.6-flash",
)

llm_request_count = LLM_REQUESTS_TOTAL.labels(
    model="gemini-3.6-flash",
)._value.get()

print(f"LLM requests recorded: {llm_request_count}")


# ============================================================
# Test 7: Record an LLM error
# ============================================================

print("\n--- Test 7: LLM Error ---")

metrics.record_llm_error(
    model="gemini-3.6-flash",
    error_type="TimeoutError",
)

llm_error_count = LLM_ERRORS_TOTAL.labels(
    model="gemini-3.6-flash",
    error_type="TimeoutError",
)._value.get()

print(f"LLM errors recorded: {llm_error_count}")


# ============================================================
# Test 8: Record LLM token usage
# ============================================================

print("\n--- Test 8: LLM Token Usage ---")

metrics.record_llm_tokens(
    model="gemini-3.6-flash",
    input_tokens=100,
    output_tokens=250,
)

input_tokens = LLM_INPUT_TOKENS_TOTAL.labels(
    model="gemini-3.6-flash",
)._value.get()

output_tokens = LLM_OUTPUT_TOKENS_TOTAL.labels(
    model="gemini-3.6-flash",
)._value.get()

print(f"Input tokens recorded: {input_tokens}")
print(f"Output tokens recorded: {output_tokens}")


# ============================================================
# Test 9: Track LLM latency
# ============================================================

print("\n--- Test 9: LLM Latency ---")

with metrics.track_llm_latency(
    model="gemini-3.6-flash",
):
    time.sleep(1.0)

llm_latency = LLM_LATENCY.labels(
    model="gemini-3.6-flash",
)

print(
    f"LLM latency total: "
    f"{llm_latency._sum.get():.4f} seconds"
)


# ============================================================
# Test 10: Record token limit exceeded
# ============================================================

print("\n--- Test 10: Token Limit Exceeded ---")

metrics.record_token_limit_exceeded(
    limit_type="input_tokens",
)

token_limit_count = TOKEN_LIMIT_EXCEEDED_TOTAL.labels(
    limit_type="input_tokens",
)._value.get()

print(f"Input token limit exceeded: {token_limit_count}")


# ============================================================
# Test 11: Record an exact cache hit
# ============================================================

print("\n--- Test 11: Exact Cache Hit ---")

metrics.record_cache_result(
    cache_type="exact",
    result="hit",
)

exact_cache_hits = CACHE_REQUESTS_TOTAL.labels(
    cache_type="exact",
    result="hit",
)._value.get()

print(f"Exact cache hits: {exact_cache_hits}")


# ============================================================
# Test 12: Record a semantic cache miss
# ============================================================

print("\n--- Test 12: Semantic Cache Miss ---")

metrics.record_cache_result(
    cache_type="semantic",
    result="miss",
)

semantic_cache_misses = CACHE_REQUESTS_TOTAL.labels(
    cache_type="semantic",
    result="miss",
)._value.get()

print(f"Semantic cache misses: {semantic_cache_misses}")


# ============================================================
# Test 13: Record cache lookup error
# ============================================================

print("\n--- Test 13: Cache Lookup Error ---")

metrics.record_cache_error(
    operation="lookup",
    error_type="ConnectionError",
)

cache_lookup_errors = CACHE_ERRORS_TOTAL.labels(
    operation="lookup",
    error_type="ConnectionError",
)._value.get()

print(f"Cache lookup errors: {cache_lookup_errors}")


# ============================================================
# Test 14: Record cache store error
# ============================================================

print("\n--- Test 14: Cache Store Error ---")

metrics.record_cache_error(
    operation="store",
    error_type="TimeoutError",
)

cache_store_errors = CACHE_ERRORS_TOTAL.labels(
    operation="store",
    error_type="TimeoutError",
)._value.get()

print(f"Cache store errors: {cache_store_errors}")


# ============================================================
# Test 15: Track cache latency
# ============================================================

print("\n--- Test 15: Cache Latency ---")

with metrics.track_cache_latency(
    cache_type="exact",
    operation="lookup"
):
    time.sleep(0.2)

cache_latency = CACHE_LATENCY.labels(
    cache_type="exact",
    operation="lookup",
)

print(
    f"Cache latency total: "
    f"{cache_latency._sum.get():.4f} seconds"
)


# ============================================================
# Test 16: Record a RAG request
# ============================================================

print("\n--- Test 16: RAG Request ---")

metrics.record_rag_request()

rag_request_count = RAG_REQUESTS_TOTAL._value.get()

print(f"RAG requests recorded: {rag_request_count}")


# ============================================================
# Test 17: Record a RAG error
# ============================================================

print("\n--- Test 17: RAG Error ---")

metrics.record_rag_error(
    error_type="RetrievalError",
)

rag_error_count = RAG_ERRORS_TOTAL.labels(
    error_type="RetrievalError",
)._value.get()

print(f"RAG errors recorded: {rag_error_count}")


# ============================================================
# Test 18: Track RAG latency
# ============================================================

print("\n--- Test 18: RAG Latency ---")

with metrics.track_rag_latency():
    time.sleep(0.7)

print(
    f"RAG latency total: "
    f"{RAG_LATENCY._sum.get():.4f} seconds"
)


# ============================================================
# Test 19: Track active requests
# ============================================================

print("\n--- Test 19: Active Requests ---")

metrics.request_started()

active_requests = ACTIVE_REQUESTS._value.get()

print(f"Active requests after start: {active_requests}")

metrics.request_finished()

active_requests = ACTIVE_REQUESTS._value.get()

print(f"Active requests after finish: {active_requests}")


# ============================================================
# Test 20: Get Metrics Summary
# ============================================================

print("\n--- Test 20: Metrics Summary ---")

summary = metrics.get_metrics_summary()

print(summary)


# ============================================================
# Test 21: Check Latency Exists In Summary
# ============================================================

print("\n--- Test 21: Summary Latency ---")

print("API latency summary:")
print(summary["api"]["latency"])

print("LLM latency summary:")
print(summary["llm"]["latency"])

print("Cache latency summary:")
print(summary["cache"]["latency"])

print("RAG latency summary:")
print(summary["rag"]["latency"])


# ============================================================
# Test 22: Prometheus Raw Output
# ============================================================

print("\n--- Test 22: Prometheus Raw Metrics ---")

prometheus_output = generate_latest().decode("utf-8")

print(prometheus_output)


# ============================================================
# Test Complete
# ============================================================

print("\n--- All Metrics Tests Completed Successfully ---")
