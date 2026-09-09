"""
This module contains generic HTTP request metrics middleware.

It records request-level observability metrics for HTTP requests,
including request count, status, latency, active requests,
and unexpected request errors.
Note that request validation is done by FastAPI/Pydantic

after passing this middleware the request will be then moved to the next step by something called call_next(request) so that FastAPI will bind this request to the necessary route

Middleware is the code that runs around every HTTP request, before it reaches the route and again after the route returns
Generic HTTP request metrics middleware.

This middleware runs around every HTTP request and records
request-level observability metrics.

It is responsible for:
- tracking active requests
- counting HTTP requests
- recording HTTP status codes
- recording request latency
- recording unexpected request errors

It does NOT:
- validate request bodies
- perform authentication or authorization
- call ChatService directly
- contain business logic


Typical middleware tasks include:
request ID
logging
request timing
active-request counter
CORS
security headers

This middleware will be useful for request-level metrics since it will be able to measure whole HTTP request without putting metric code inside every endpoint
So, one benifit is that this middleware will be used before the routes and it reusable for all endpoints or the endpoint that we want to sepecify

So, for now this middleware will be used to record the request time and the request count for the chat endpoint, but in the future it can be used for other endpoints as well.

HTTP request
   ↓
mark request active
   ↓
start timer
   ↓
execute route
   ↓
capture HTTP status
   ↓
record request metrics
   ↓
record latency
   ↓
mark request finished


note: one thing to update: 

we already have the following helper in the metrics.py file:
with metrics.track_request_latency(
    method="POST",
    endpoint="/api/chat",
):
    ...
The above is useful when we have a single endpoint, since we can already know the endpoint name before starting the timer
and the problem with generic middleware is that it runs before the FastAPI has selected the route and we don't know the endpoint name yet.

Request arrives
    ↓
Middleware starts        ← we are here
    ↓
FastAPI routing
    ↓
FastAPI determines:
"/api/chat"
"/api/users/{user_id}"
etc.
    ↓
Route executes

At the beginning of the middleware, we know the raw URL request.url.path => /api/chat but later in case we have @router.get("/users/{user_id}") 
three requests could be => 1- /api/users/1, 2- /api/users/2, 3- /api/users/3
so if Prometheus is going to record the metrics for the endpoint, it will record three different endpoints labels => /api/users/1, /api/users/2, /api/users/3

so we need to build a new helper that will with is record_request_latency()

def record_request_latency(
    self,
    method: str,
    endpoint: str,
    duration_seconds: float,
) -> None:
    REQUEST_LATENCY.labels(
        method=method,
        endpoint=endpoint,
    ).observe(duration_seconds) 
    
this method is another helper method that will also manipulate the same counter REQUEST_LATENCY but the main difference is that this method will not calculate the duration of the request, it will just record the duration that is passed to it as an argument
this is necessary since the other helper method track_request_latency() is a context manager that where will excute the request code inside it so it calculates the duration or start and stop the timer
but the thing is that we don't know the endpoint name at the beginning of the middleware, so we can't use the context manager since it will calculate the duration before we know the endpoint name

the best appraoch is that we will start the timer at the beginning of the middleware and then after the route is executed, we will stop the timer and then we will call the record_request_latency() method and pass the duration to it along with the method and endpoint name.

duration = 1.25

metrics.record_request_latency(
    method="POST",
    endpoint="/api/chat",
    duration_seconds=duration,
)

BEFORE route
start_time = perf_counter()

        ↓ request runs ↓

AFTER route
duration = perf_counter() - start_time

Now we know the matched route
        ↓
record the duration




"""


# app/middleware/request_middleware.py


# this one will allow us to use per_counter() which gives us a high-resolution timer that is suitable for measuring short durations, such as the time taken to process an HTTP request
from time import perf_counter

# this imports the Request Object from fastapi that represents the incoming HTTP request
# it gives us things such as
# request.method => GET, POST, PUT, DELETE
# request.url => the full URL of the request
# request.headers => the headers of the request
# request.body() => the body of the request
# request.query_params => the query parameters of the request
# request.scope => the scope of the request, which contains information about the request such as the route, path, and other metadata
from fastapi import Request

# this is the base class we are extending to create middleware that will run before and after every HTTP request
from starlette.middleware.base import BaseHTTPMiddleware

from starlette.responses import Response
from app.core.monitoring.logging import get_logger
from app.core.monitoring.metrics import metrics

"""
The difference between the endpoint, url, route and path:
- endpoint: The route template that matches the request (e.g., /api/users/{user_id})
- url: The full URL of the request <=> The complete address of the request (e.g., https://example.com/api/users/123)
=> for example request.url => it contains more information than we need for metrics such as
1- scheme: https
2- host: example.com
3- path: /api/users/123
4- query parameters: ?page=1&limit=10
=> https://example.com/api/users/123?include_orders=true

- path: The path component of the URL <=> The URL part after the domain (e.g., /api/users/123)
=> for example the request.url.path => /api/users/123 
and it differs from one request to another since it could be /api/users/123 or /api/users/456 or /api/users/789
This is the main problem is that we don't want to allow prometheus to record metrics for each individual request since it will create high-cardinality metrics and it will be hard to analyze the metrics later on
=> the solution is to use the route template that matches the request instead of the actual path of the request

- route: The route object that represents the matched route <=> FastAPI/Starlette route object
- route template: The generic route pattern defined in your application => /api/users/{user_id}


for our helper record_latency() what we need is the route template that matches the request, so that we can use it to record the metrics for the endpoint
the route template is the what we define in the route decorator, for example:
@router.get("/users/{user_id}")
async def get_user(user_id: str):

and the actual request is something like this:
GET /users/123 HTTP/1.1

route template can't be identified unless we process the request and let FastAPI match the request to the route, so we need to do this after the route is executed, so that we can get the matched route template and use it to record the metrics for the endpoint
by using the request.scope.get("route") we can get the route object that matches the request and then we can get the route template from it by using getattr(route, "path", None)

this is done in the _get_endpoint() method that will return the matched route template for the request, so that we can use it to record the metrics for the endpoint

for our /api/chat endpoint we have no dynamic parameter: @router.post("/chat") 
but this middleware could handle endpoints with dynamic parameters such as @router.get("/users/{user_id}") and it will return the matched route template for the request, so that we can use it to record the metrics for the endpoint
"""


logger = get_logger(__name__)


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """
    Generic HTTP request metrics middleware.

    Responsibilities:
    - Track active requests.
    - Record HTTP request count and status.
    - Record request latency.
    - Record unexpected request errors.

    This middleware does NOT contain:
    - Request validation
    - Authentication
    - Authorization
    - Business logic
    - Chat-specific logic
    """

    # this one is just a helper method that will return the matched route template for the request, so that we can use it to record the metrics for the endpoint
    @staticmethod
    def _get_endpoint(request: Request) -> str:
        """
        Return the matched route template.

        Example:
            /api/users/123
        becomes:
            /api/users/{user_id}

        Unmatched requests use a fixed label to prevent
        high-cardinality Prometheus metrics.
        """

        route = request.scope.get("route")

        if route is not None:
            route_path = getattr(route, "path", None)

            if route_path:
                return route_path

        return "__unmatched__"

    async def dispatch(
        self,
        request: Request,
        # The function that allows the request to continue through the application.
        call_next,
    ) -> Response:

        method = request.method
        start_time = perf_counter()

        # ------------------------------------------------------------
        # REQUEST START
        # ------------------------------------------------------------
        """
        metrics.request_started(): fails before successfully incrementing the active-request gauge.
        metrics.request_finished(): could decrement the active-request gauge below zero if request_started() failed.
        to solve this we will use the flag below
        """

        active_request_recorded = False

        try:
            metrics.request_started()
            active_request_recorded = True
        except Exception:
            logger.exception(
                "Failed to record active request start metric"
            )

        try:
            # Continue processing the HTTP request.
            response = await call_next(request)

            endpoint = self._get_endpoint(request)

            try:
                metrics.record_request(
                    method=method,
                    endpoint=endpoint,
                    status=str(response.status_code),
                )
            except Exception:
                logger.exception(
                    "Failed to record request metric"
                )

            return response

        except Exception as exc:

            endpoint = self._get_endpoint(request)

            # Count the failed HTTP request.
            try:
                metrics.record_request(
                    method=method,
                    endpoint=endpoint,
                    status="500",
                )
            except Exception:
                logger.exception(
                    "Failed to record failed request metric"
                )

            # Record the specific unexpected error.
            try:
                metrics.record_request_error(
                    endpoint=endpoint,
                    error_type=type(exc).__name__,
                )
            except Exception:
                logger.exception(
                    "Failed to record request error metric"
                )

            raise

        finally:

            duration_seconds = perf_counter() - start_time
            endpoint = self._get_endpoint(request)

            try:
                metrics.record_request_latency(
                    method=method,
                    endpoint=endpoint,
                    duration_seconds=duration_seconds,
                )
            except Exception:
                logger.exception(
                    "Failed to record request latency metric"
                )
            if active_request_recorded:
                try:
                    metrics.request_finished()
                except Exception:
                    logger.exception(
                        "Failed to record active request finish metric"
                    )


"""
POST /api/chat
       ↓
RequestMetricsMiddleware
       ↓
call_next(request)
       ↓
FastAPI router
       ↓
Chat route
       ↓
Depends(get_chat_service)
       ↓
ChatService.process()
       ↓
Security
       ↓
Token budget
       ↓
Cache
       ↓
Agent / LLM
       ↓
ChatResponse
       ↑
       ↑
response returns to middleware
"""
