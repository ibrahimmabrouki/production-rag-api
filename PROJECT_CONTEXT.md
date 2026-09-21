# Production-RAG-API — Project Context

## 1. Purpose of This File

This file is the development handoff and continuity document for the
Production-RAG-API project.

The source code is the source of truth for what is currently implemented.
This document explains the broader context that may not be obvious from the
code alone, including:

- What the project is intended to become.
- The architecture being developed.
- What has already been implemented.
- Important architectural decisions.
- What has already been tested.
- Known issues and intentionally deferred work.
- Where development currently stopped.
- What should be implemented next.

When starting a new development conversation, inspect the current source code
and use this document to understand the development history before suggesting
changes.

If this document conflicts with newer source code, prefer the newer source
code and point out the discrepancy when relevant.

# 2. Project Vision

Production-RAG-API is intended to become a production-ready, configurable RAG
platform.

The long-term goal is to allow developers or other users to build and operate
RAG systems while choosing/configuring components according to their needs.

This is not intended to remain a simple RAG demo or a single-purpose chatbot.

The platform should progressively provide configurable services for areas such
as:

- Document ingestion.
- Multiple document chunking strategies.
- Multiple retrieval strategies.
- Semantic/vector search.
- Keyword search.
- Hybrid search.
- Web search.
- Vector database integration.
- Configurable RAG pipelines.
- Agent-based workflows.
- Primary and fallback LLM strategies.
- Security.
- Input/output validation and sanitization.
- Token budgeting and usage limits.
- Exact and semantic caching.
- Error handling and resilience.
- Logging.
- Metrics.
- Distributed/application tracing.
- Monitoring and observability.
- Prometheus-compatible metrics.
- External observability platforms.
- APIs exposing these capabilities to developers.

The current implementation is being built incrementally. Individual
production modules are implemented and validated before being integrated into
the complete API.

# 3. High-Level Target Architecture

The general request flow being developed is:

Client
↓
FastAPI API
↓
Request-level observability
↓
Security Pipeline
├── Input PII handling
├── Injection/security checks
└── Output security
↓
Token Budget / Usage Limits
↓
Cache Manager
├── Exact Cache
└── Semantic Cache
↓
RAG / Agent Layer
├── Retrieval
├── LLM
└── Fallback strategy
↓
Output Security
↓
Cache Safe Response
↓
API Response

Cross-cutting concerns include:

- Logging
- Metrics
- Tracing
- Error handling
- Monitoring
- Security
- Usage accounting

# 4. Current Technology Direction

Current project technologies/components include:

- Python
- FastAPI
- Redis
- Prometheus-compatible metrics
- LangGraph / agent workflow
- Google Gemini as the current LLM provider
- LangSmith tracing
- Grafana Cloud / Alloy for observability infrastructure

Redis currently runs in Docker while the FastAPI application runs locally.

The project currently uses Pydantic Settings for application configuration.

# 5. Development Approach

The project is intentionally being developed module-by-module.

The general approach has been:

1. Build a production module.
2. Validate it independently.
3. Integrate it with the application.
4. Verify its behavior.
5. Move to the next architectural concern.

Avoid rewriting working modules without a technical reason.

Production concerns such as failure handling, concurrency, security,
observability, scalability, and clean dependency boundaries should be
considered during implementation.

# 6. Major Modules Developed So Far

The project already contains implementations around the following areas.

## Security

A SecurityPipeline exists and is integrated into ChatService.

The chat workflow performs input security processing before expensive
downstream work.

Security-related observability has also been incorporated.

The system also performs output security processing before returning/caching
generated responses.

## Token Budgeting

A TokenBudget component exists.

Token controls include multiple layers of checking.

The current ChatService flow includes:

- Per-request token validation.
- Existing chat usage retrieval.
- Layer 1 budget checking.
- Atomic request reservation / Layer 2 protection.
- Output token usage handling.

A ChatUsageRepository is used for usage-related persistence/accounting.

Token limit events have metrics associated with them.

## Cache

A CacheManager exists and is integrated into ChatService.

The cache architecture supports:

- Exact cache.
- Semantic cache.

Cache lookup occurs before expensive agent/LLM execution.

The cache follows fail-open behavior in appropriate situations. A cache
failure should not automatically make the entire user request fail if the
request can still be processed normally.

Cache-related metrics have been implemented.

## Agent / LLM

A ProductionAgent exists.

The agent invocation is currently synchronous, so ChatService invokes it using:

    await asyncio.to_thread(...)

This prevents synchronous agent execution from directly blocking the FastAPI
event loop.

The agent architecture includes primary/fallback model concepts.

The current provider is Google Gemini.

The fallback may currently use the same underlying model/provider depending on
available configuration. Do not treat that as an unknown bug unless the
configuration has since changed.

Agent/LLM metrics have been added.

## Observability

Observability is treated as a first-class architectural concern.

The project contains work around:

- Structured/application logging.
- Prometheus metrics.
- LangSmith tracing.
- Grafana Cloud / Alloy.

Metrics should be fail-open: a metrics failure should not break the core
application request.

Prometheus labels must remain low-cardinality.

Do not use values such as:

- user IDs
- thread IDs
- raw prompts
- raw responses
- arbitrary error messages

as Prometheus labels.

# 7. ChatService

ChatService is currently the main orchestration layer for chat request
processing.

Its general workflow is:

1. Process input security.
2. Validate per-request token limits.
3. Load existing chat usage.
4. Perform Layer 1 budget validation.
5. Perform atomic request reservation / Layer 2 protection.
6. Check cache.
7. Handle cache hit if available.
8. On cache miss, invoke ProductionAgent.
9. Validate/normalize agent result.
10. Perform output security processing.
11. Record output token usage.
12. Cache a safe response when appropriate.
13. Return the result.

Some non-critical downstream operations intentionally follow fail-open
behavior when a valid user response is already available.

# 8. Application Dependency Lifecycle

Expensive/shared application components are intended to be initialized once
during FastAPI lifespan rather than recreated per request.

The lifespan initializes shared components and places them on:

    app.state

Examples include components such as:

- SecurityPipeline
- CacheManager
- TokenBudget
- ProductionAgent
- ChatUsageRepository
- ChatService

FastAPI dependency functions retrieve these shared instances from:

    request.app.state

This avoids unnecessarily rebuilding expensive services for every HTTP
request.

# 9. Metrics Singleton Decision

The metrics collector is different from the application services above.

The project uses a module-level metrics singleton:

    metrics = MetricsCollector()

Modules import this shared metrics object directly.

Do NOT unnecessarily:

- initialize MetricsCollector in lifespan,
- place it in app.state,
- create a FastAPI dependency just to retrieve the metrics singleton.

This was an intentional architectural decision.

# 10. API Structure

The API currently follows a structure similar to:

app/
└── api/
├── route_classes/
│ └── metrics_route.py
├── routes/
│ ├── chat.py
│ ├── health.py
│ └── metrics.py
└── router.py

The central API router includes:

- Chat routes.
- Health routes.
- Metrics routes.

The main FastAPI application includes the central router with the `/api`
prefix.

Therefore current endpoints include concepts such as:

- POST /api/chat
- GET /api/health
- GET /api/metrics

# 11. Request-Level Metrics Architecture

A key architectural decision was made for HTTP request metrics.

The requirement was:

Request-level metrics should currently apply to the chat API without
unnecessarily measuring endpoints such as:

- health
- metrics scraping
- documentation

FastAPI APIRouter does not provide Express-style router middleware.

Therefore global HTTP middleware was NOT used for this requirement.

Instead, a custom APIRoute implementation was created:

    MetricsAPIRoute

The chat router uses:

    APIRouter(route_class=MetricsAPIRoute)

Health and metrics routes continue using normal APIRouter behavior.

# 12. Important APIRouter / APIRoute Mental Model

Keep this distinction when explaining the custom request metrics architecture.

APIRouter
= collection/registry of routes

APIRoute
= representation of one route

chat()
= endpoint function

Normally:

    router = APIRouter()

    @router.post("/chat")
    async def chat(...):
        ...

FastAPI internally creates an APIRoute representing that endpoint.

Conceptually:

APIRoute
path = "/chat"
methods = {"POST"}
endpoint = chat

The normal flow is approximately:

POST /chat
↓
FastAPI/Starlette routing
↓
matching APIRoute
↓
APIRoute.get_route_handler()
↓
request validation
↓
dependency resolution
↓
chat()
↓
response validation/serialization
↓
Response

MetricsAPIRoute subclasses APIRoute and overrides get_route_handler().

It first obtains the normal FastAPI handler using:

    super().get_route_handler()

It then wraps that handler with request-level metrics.

Conceptually:

POST /api/chat
↓
MetricsAPIRoute
↓
start metrics
↓
normal FastAPI route handler
↓
validation
↓
dependencies
↓
chat endpoint
↓
response
↓
record request metrics
↓
return Response

# 13. Request Metrics Implemented

The request-level metrics work currently includes concepts such as:

- Total requests.
- Request status.
- Request latency.
- Active requests.
- Request errors.

The route wrapper uses the existing MetricsCollector instead of implementing
Prometheus logic directly inside the route class.

Latency is tracked using the MetricsCollector latency context manager.

Active request tracking is guarded so the finish/decrement operation only
happens when the start/increment operation succeeded.

The wrapper rethrows unexpected exceptions after recording relevant metrics so
normal application exception handling can continue.

# 14. Metrics Endpoint

A Prometheus metrics endpoint has been exposed through the API.

The metrics output was manually inspected.

The output correctly contained standard Python/process metrics and the
project's custom metrics definitions.

Examples of custom metric areas included:

- Security checks.
- API requests.
- API errors.
- Request duration.
- LLM requests.
- RAG requests.
- Active requests.

An active request gauge value of 0 when no request is currently running is
expected.

Some labeled metrics may show HELP/TYPE definitions without samples until the
first matching observation occurs.

# 15. Prometheus Interpretation Notes

Important concepts already discussed:

HELP
Human-readable description of a metric.

TYPE
Prometheus metric type.

Counter
Normally increases over time.

Gauge
Can increase and decrease.

Histogram
Records distributions such as request duration.

Histogram `_count`
Number of observations.

Histogram `_sum`
Total observed value.

Histogram buckets
Cumulative counts for values less than or equal to (`le`) a threshold.

Detailed request-metric verification was intentionally paused and can be
returned to later.

# 16. Current API Status

The FastAPI application successfully starts.

The `/api/chat` route is wired to ChatService.

The shared dependencies are initialized through lifespan and retrieved through
FastAPI dependencies.

The `/api/metrics` endpoint is exposed.

The chat-only MetricsAPIRoute is wired.

The application has successfully processed chat requests.

# 17. Current Important Problem

Development currently stopped while investigating HTTP error semantics.

A real Gemini provider failure exposed the issue.

Gemini returned an upstream quota/rate-limit error similar to:

    429 RESOURCE_EXHAUSTED

The provider indicated that the free-tier request quota had been exceeded.

The internal application correctly recognized that the agent failed.

However, the external FastAPI request still returned:

    HTTP 200 OK

This is currently incorrect API behavior.

# 18. Root Cause of the HTTP 200 Problem

The current flow is approximately:

Gemini/provider failure
↓
ProductionAgent produces an error result
↓
ChatService detects the agent error
↓
ChatService returns a normal Python dictionary:

    {
        "success": False,
        "error": "...",
        ...
    }

↓
chat route constructs/returns ChatResponse
↓
FastAPI sees a normal successful endpoint return
↓
HTTP 200

Therefore:

    success=False

inside the JSON body does NOT automatically change the HTTP status code.

This also means HTTP request metrics currently see a real HTTP 200, because
that is genuinely the response status being produced by the API.

# 19. Direction Chosen for Error Handling

Do NOT solve this by parsing/string-matching human-readable error messages in
the API route.

Do NOT tightly couple ChatService to FastAPI by raising FastAPI HTTPException
directly from the service layer without considering the architecture.

The application needs machine-readable/domain-level error information.

A direction discussed was introducing an error code concept, for example:

    {
        "success": False,
        "error_code": "LLM_RATE_LIMIT",
        "error": "..."
    }

Possible error categories may eventually include concepts such as:

- LLM_RATE_LIMIT
- TOKEN_LIMIT_EXCEEDED
- SECURITY_BLOCKED
- LLM_SERVICE_ERROR
- USAGE_SERVICE_ERROR
- RESPONSE_PROCESSING_ERROR
- INTERNAL_ERROR

Exact names and architecture should be finalized carefully before applying
them everywhere.

# 20. Important Error-Handling Design Constraint

The HTTP status solution must work correctly with MetricsAPIRoute.

MetricsAPIRoute currently observes:

    response.status_code

for successfully returned Response objects.

If the endpoint raises FastAPI HTTPException and the custom APIRoute catches it
as a generic Exception before FastAPI converts it into an HTTP response, the
metrics wrapper could incorrectly record HTTP 500 instead of the intended
status such as 429.

Therefore the HTTP error design must be implemented together with awareness of
the request-metrics wrapper.

Possible solutions include:

- Returning an explicit response with the intended status code.
- Teaching MetricsAPIRoute to distinguish HTTPException from unexpected
  exceptions.
- Moving toward domain exceptions plus centralized FastAPI exception handlers.

Do not implement one of these blindly. Inspect the latest code and choose the
cleanest production architecture.

# 21. Provider Error Classification

The current Gemini error may reach ChatService through an agent result.

Avoid classifying provider failures by searching arbitrary strings such as
"RESOURCE_EXHAUSTED" inside error messages if structured provider error
information can instead be propagated from the agent/provider layer.

If necessary, inspect the current ProductionAgent and relevant agent nodes
before implementing provider-specific classification.

# 22. Fail-Open vs Fail-Closed Behavior

Not every internal failure should automatically fail the HTTP request.

Examples of operations intentionally treated as fail-open in appropriate
situations include cache operations.

If cache lookup fails but the agent can still produce a valid answer, the
request can continue.

Similarly, some bookkeeping failures after a valid response exists may not
need to destroy the user response.

Security, usage enforcement, LLM generation, and internal processing failures
need to be evaluated according to their responsibility and failure semantics.

Preserve these distinctions rather than applying one generic error policy to
all exceptions.

# 23. Current Development Position

Completed/integrated at the current stage:

- Core security module integration.
- Token budgeting integration.
- Chat usage handling.
- Exact/semantic cache integration.
- ProductionAgent integration.
- LLM metrics.
- Cache metrics.
- Security metrics.
- Logging.
- Tracing infrastructure.
- Shared FastAPI lifespan dependencies.
- ChatService wiring.
- Chat API route.
- Health route.
- Prometheus metrics endpoint.
- Custom MetricsAPIRoute.
- Chat-only HTTP request instrumentation.
- FastAPI application startup.
- Successful `/api/chat` execution.

Paused/deferred:

- Detailed Prometheus request-metric verification.
- RAG-specific metrics until the actual RAG service/pipeline exists.
- Some production observability concerns such as multi-worker Prometheus
  behavior.
- Final centralized exception-handling architecture.
- Authentication/authorization middleware may be added later.

# 24. EXACT CURRENT TASK

The current task is:

DESIGN AND IMPLEMENT CORRECT ERROR PROPAGATION FROM THE APPLICATION/SERVICE
LAYERS TO THE HTTP API.

The immediate problem to solve is:

    ChatService failure
        ↓
    success=False
        ↓
    currently HTTP 200

The desired behavior is:

    ChatService/domain failure
        ↓
    structured failure classification
        ↓
    API maps failure appropriately
        ↓
    correct HTTP status
        ↓
    MetricsAPIRoute observes the correct status

# 25. EXACT NEXT STEP

Before modifying all ChatService failure paths, finalize the structured error
representation.

The previously discussed immediate starting point was to introduce a
machine-readable error-code concept to the API/application response model.

For example:

    error_code: str | None = None

However, before applying broad changes:

1. Inspect the latest ChatResponse model.
2. Inspect the latest ChatService.
3. Inspect the current ProductionAgent/provider error flow if necessary.
4. Decide how structured domain failures should propagate.
5. Ensure the design works with MetricsAPIRoute.
6. Then modify failure paths incrementally.

Do not redesign unrelated parts of the application while doing this.

# 26. Work After the Current Error-Handling Task

After correct HTTP error handling is implemented and verified, likely upcoming
work includes:

- Centralized exception handling.
- Completing/verifying HTTP request metrics.
- Continuing RAG pipeline implementation.
- Retrieval architecture.
- Vector database integration.
- Document ingestion.
- Chunking strategies.
- Semantic/vector search.
- Keyword search.
- Hybrid search.
- Web search.
- RAG-specific observability.
- Authentication/authorization when appropriate.
- Further production hardening.

This list is directional, not a strict implementation order.

Always determine the actual next step from the latest source code and latest
development state.

# 27. Development Rules for Future Sessions

When continuing this project:

1. Inspect the actual repository before assuming implementation details.
2. Treat current source code as the implementation source of truth.
3. Use this file for historical and architectural context.
4. Do not invent files or features.
5. Do not restart development from scratch.
6. Do not unnecessarily redesign working modules.
7. Continue from the current development position.
8. Work one meaningful step at a time.
9. Explain unfamiliar concepts simply.
10. Prefer production-quality solutions.
11. Verify important changes before moving forward.
12. Keep the system's long-term platform vision in mind without
    overengineering the current stage.

# 28. Repository Continuity

The repository is intended to be the live source for ChatGPT development
sessions.

After meaningful local changes:

    local development
        ↓
    git commit
        ↓
    git push
        ↓
    GitHub repository
        ↓
    ChatGPT inspects latest repository state

Update this PROJECT_CONTEXT.md when an important milestone, architectural
decision, current task, or next step changes.

It does not need to be updated after every small code edit.

Its purpose is to make a new development session capable of understanding:

    What are we building?
    What have we already built?
    Why was it built this way?
    What has been verified?
    Where did we stop?
    What should we do next?
