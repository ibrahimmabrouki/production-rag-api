
"""
Here is the metrics collector which is going to track everyhting we want to care about

we can have the below approach which is commanded but it has some limitations:
- it stores the metrics in Python memory, which means that if the application restarts, we will lose all the metrics.
- and if we create three API workers, each of these APIs will have its own counters so the totals are not automatically combined because theses counters are not stored in shared memory or a database.

Since this is a production level api then we need to make everything reliable:
For productin we will use the officail Prometheus client for python: it is specially designed around counters, gauges, histograms and summaries.

first we need to install the package => use: uv add prometheus-client

and we need to import it: from prometheus_client import Counter, Gauge, Histogram

your Python metrics → Prometheus → Grafana

1- What is Prometheus?

Prometheus is a monitoring system

This application produces mreasurements such as: 

API requests = 15,000
API errors = 23
Gemini requests = 8,000
Cache hits = 6,500
Average/percentile latency = ...
Active requests = 7

This prometheus_client Python package is not the Prometheus server it self, but it is just a library the FastAPI application that: 

- keeps metric values for that Python process;
- formats them in Prometheus's standard format;
- exposes them so an external Prometheus-compatible system can collect them.

FastAPI
   │
   ├── prometheus_client
   │      ├── Counters
   │      ├── Gauges
   │      └── Histograms
   │
   ▼
/metrics
   │
   ▼
Prometheus
   │
   ▼
Grafana

2- Where are the metrics actually located

When we run the FastAPI server (uvicorn app.main:app) => The inside the application REQUESTS_TOTAL = Counter(...) and rest couters, gauge and histograms live in the memory (RAM) of that python process

Your PC
│
├── Python/FastAPI process
│     │
│     ├── REQUESTS_TOTAL = 100
│     ├── CACHE_REQUESTS_TOTAL = 40
│     └── LLM_REQUESTS_TOTAL = 60
│
└── RAM

=> It is not automatically stored in Redis, PostgreSQL, or a file.
=> If that Python process dies/restarts, those in-process values disappear.

3. What does Prometheus do with /metircs

Eventually the FastAPI application will expose something similar to GET /metrics which returns something like:

- rag_api_requests_total{method="POST",endpoint="/chat",status="200"} 150

- rag_api_llm_requests_total{model="gemini-3.6-flash"} 80

- rag_api_cache_requests_total{cache_type="exact",result="hit"} 50

by making sure that this endpoint is exposed by FastAPI, and Prometheus server can scrape it (read it) every 15 seconds, and store the values in its own database, and then Grafana can read from Prometheus and visualize the metrics.

we will then have: 

Every 15 seconds

Prometheus (GET /metrics) => FastAPI => current metric values => Prometheus stores them
===> Prometheus pulls metrics from your application rather than your application continuously sending each metric event to Prometheus.

4. What happens with multiple FastAPI workers?

case-1: 
When you have multiple FastAPI workers, each worker runs in its own process and maintains its own set of metrics in memory.

so, how Prometheus handle multiple workers?
With seperate application instances/containers, Prometheus normally scrapes each instance separately:

FastAPI Instance 1       FastAPI Instance 2       FastAPI Instance 3
Port 8001                Port 8002                Port 8003
requests = 100           requests = 80            requests = 120
     │                         │                         │
     ▼                         ▼                         ▼
 /metrics:8001             /metrics:8002             /metrics:8003
     │                         │                         │
     └──────────────┬──────────┴─────────────────────────┘
                    ▼
                Prometheus
             
Then Prometheus queries can aggregate them for instance: sum(rag_api_requests_total) => 300

Case-2:

When we have one FastAPI server with 3 Uvicorn workers for example: uvicorn app.main:app --workers 3
=> we expose only one /metrics endpoint on localhost:8000/metrics, but internally each worker maintains its own set of metrics in memory.

                 localhost:8000
                       │
                ┌──────┴──────┐
                │             │
           OS distributes requests
             /        |        \
            ▼         ▼         ▼
        Worker 1   Worker 2   Worker 3
        RAM: 100   RAM: 80    RAM: 120
    
=> Prometheus scrapes the /metrics endpoint: GET localhost:8000/metrics
=> HTTP request gets handled by one worker assume worker 2 and worker 2 knows only requests = 80 so Prometheus could receive 80 and not the combined 300

The workers are separate processes sharing the same listening service/port.

and this is not easy for Prometheus to aggregate the metrics from multiple workers because they are not seperately addressebable and Prometheus cannot choose worker 1, 2 ,3 individually

and thats why Python Prometheus multi-process mode exists => it gives the workers a way to contribute their metrics to a common collection mechanism

Worker 1 ──┐
           │
Worker 2 ──┼──→ shared Prometheus multiprocess directory
           │
Worker 3 ──┘
                     │
                     ▼
                  /metrics
                     │
                     ▼
                 Prometheus
                 
So, In general: 

- Separate servers/containers: Prometheus can scrape each one separately and aggregate them.

- Multiple workers behind one FastAPI port: Prometheus cannot directly target each worker, so the Python client needs multiprocess handling to aggregate their metrics correctly.


Now after defining the metrics we can and creating the MetricsCollector class that defines the wrapper methods to update the metrics

not all of them are going to be added to the chat sevrice directly, but we will use them in the correct module

For example:

1- Security metrics should be used in the ChatService: 
- input allowed / blocked
- output safe / blocked

2- Token-Limit metrics should be used in the ChatService:
- input token limit exceeded
- chat token limit exceeded
- request-count limit exceeded

3- Cache metrics should be used in the CacheManager:
- exact hit/miss
- semantic hit/miss
- cache latency
- lookup/store errors

4- LLM metrics in ProductionAgent:
- request count per model
- error count per model
- latency per model
- input/output token usage

5- RAG metrics in the RAG/agent layer
- RAG executions
- RAG errors
- RAG latency

6- API metrics last
- request count
- request errors
- request latency
- active requests
"""
# from typing import Callable, Any, Optional
# from functools import wraps
# from datetime import datetime, timezone
# import time
# import json
# import logging

# context manager is a way that allow us to perform something that allows to perform something before a block of code and something after a block of code
# START => setup => do_work() =>cleanup
from contextlib import contextmanager

# An iterator is an object that gives you values one at a time.
# it has similar anology as the following:
# numbers = [10, 20, 30]
# for number in numbers:
#     print(number)

# Python internally gets the values one by one.
# Iterator = something that can produce values one at a time
from typing import Iterator
from prometheus_client import Counter, Gauge, Histogram

from app.core.monitoring.logging import get_logger

logger = get_logger(__name__)

SECURITY_CHECKS_TOTAL = Counter(
    "rag_api_security_checks_total",
    "Total security checks.",
    ["stage", "result"],
)
"""
Example usage:
stage=input,  result=allowed
stage=input,  result=blocked
stage=output, result=safe
stage=output, result=blocked

input + allowed = 10,000
input + blocked = 150
=> 150 requests were rejected by input security.

"""


# API Request metrics
REQUESTS_TOTAL = Counter(
    "rag_api_requests_total",
    "Total number of API requests.",
    ["method", "endpoint", "status"],
)

# REQUESTS_TOTAL.labels(
#     method="POST",
#     endpoint="/chat",
#     status="200",
# ).inc()

REQUEST_ERRORS_TOTAL = Counter(
    "rag_api_errors_total",
    "Total number of API errors.",
    ["endpoint", "error_type"],
)

REQUEST_LATENCY = Histogram(
    "rag_api_request_duration_seconds",
    "API request duration in seconds.",
    ["method", "endpoint"],
)

# 0.1 sec
# 0.2 sec
# 0.3 sec
# 0.3 sec
# 0.4 sec
# 5.0 sec
# An average could hide the fact that one request took 5 seconds.

# REQUEST_LATENCY.labels(
#     method="POST",
#     endpoint="/chat",
# ).observe(1.25)


# LLM metrics

LLM_REQUESTS_TOTAL = Counter(
    "rag_api_llm_requests_total",
    "Total number of LLM requests.",
    ["model"],
)

# gemini-3.6-flash → 500 requests
# gemini-1.5-turbo → 20 requests


LLM_ERRORS_TOTAL = Counter(
    "rag_api_llm_errors_total",
    "Total number of LLM errors.",
    ["model", "error_type"],
)

# Which model?
# What error?
# How many times?


LLM_LATENCY = Histogram(
    "rag_api_llm_duration_seconds",
    "LLM request duration in seconds.",
    ["model"],
)
# Gemini:
# 100 ms
# 200 ms
# 300 ms
# 800 ms
# 2 sec

LLM_INPUT_TOKENS_TOTAL = Counter(
    "rag_api_llm_input_tokens_total",
    "Total number of input tokens sent to the LLM.",
    ["model"],
)


LLM_OUTPUT_TOKENS_TOTAL = Counter(
    "rag_api_llm_output_tokens_total",
    "Total number of output tokens generated by the LLM.",
    ["model"],
)

TOKEN_LIMIT_EXCEEDED_TOTAL = Counter(
    "rag_api_token_limit_exceeded_total",
    "Total requests rejected because a token or request limit was exceeded.",
    ["limit_type"],
)

"""
TOKEN_LIMIT_EXCEEDED_TOTAL.labels(
    limit_type="input_tokens"
).inc()

TOKEN_LIMIT_EXCEEDED_TOTAL.labels(
    limit_type="chat_usage"
).inc()

"""


# input tokens → tokens sent to LLM
# output tokens → tokens generated by LLM


# Cache metrics
CACHE_REQUESTS_TOTAL = Counter(
    "rag_api_cache_requests_total",
    "Total number of cache lookups.",
    ["cache_type", "result"],
)

# CACHE_REQUESTS_TOTAL.labels(
#     cache_type="exact",
#     result="hit",
# ).inc()

# CACHE_REQUESTS_TOTAL.labels(
#     cache_type="semantic",
#     result="hit",
# ).inc()

# exact + hit
# exact + miss

# semantic + hit
# semantic + miss

CACHE_LATENCY = Histogram(
    "rag_api_cache_duration_seconds",
    "Cache operation duration in seconds.",
    ["cache_type", "operation"],
)

"""
Some times cache lookups fails so it is not even a hit or a miss, it is an error due to an exception happend in get method overall
or even it could happen on the set method when we try to store the reoponse

both of them are not even a reason to not return a response to the user

operation=lookup
error_type=ConnectionError

operation=store
error_type=TimeoutError

"""


CACHE_ERRORS_TOTAL = Counter(
    "rag_api_cache_errors_total",
    "Total cache errors.",
    ["operation", "error_type"],
)


# Rag metrics
RAG_REQUESTS_TOTAL = Counter(
    "rag_api_rag_requests_total",
    "Total number of RAG pipeline executions.",
)

RAG_ERRORS_TOTAL = Counter(
    "rag_api_rag_errors_total",
    "Total number of RAG pipeline errors.",
    ["error_type"],
)

RAG_LATENCY = Histogram(
    "rag_api_rag_duration_seconds",
    "RAG pipeline execution duration in seconds.",
)


# Unlike a Counter, a Gauge can go up and down. Prometheus recommends gauges for values representing current state, such as concurrent requests.
# ACTIVE_REQUESTS.inc()
# try:
#     # process request
#     ...
# finally:
#     ACTIVE_REQUESTS.dec()
# Active requests gauge
ACTIVE_REQUESTS = Gauge(
    "rag_api_active_requests",
    "Number of requests currently being processed.",
)

"""
Why using the above approach is better:
since: -self._request_total += 1- is just a python variable

while Prometheus uses proper metric types: for example, Counter is a metric type that can only go up, and it is designed to be used in a multi-threaded environment.
REQUESTS_TOTAL.inc() this means increase the counter by 1, and it is thread-safe, so if we have multiple threads incrementing the same counter, it will be handled correctly.

for the latency the regular appraoch will give the average and hides for example if some Request is taking too much time than others

while with Prometheus we can have a histogram which will give us the distribution of the latencies, and we can see if there are any outliers of if the latency is increasing over time, and we can also set up alerts based on the histogram.

                    FastAPI
                       │
                       ▼
              Security Pipeline
                       │
                       │ metrics
                       ▼
                Cache Manager
                 /          \
                /            \
       Exact Cache       Semantic Cache
               |           |
               ▼           ▼
                  Cache Miss
                       │
                       ▼
                 RAG Pipeline
                       │
                       ▼
                      LLM
                       │
                       │ metrics
                       ▼
                    Response
"""

# now after defining the variables above we can create the MetricsCollector class which will be used to collect the metrics and expose them to Prometheus/Grafana Cloud later on


class MetricsCollector:
    """
    Central interface for recording application metrics

    Other parts of the application should use this class instead of interacting directly with Prometheus metrics.
    """

    # ===================================
    # Security
    # ===================================

    """
    This method is responsible for recording the security check metrics, which means it will increase the security check counter 
     and it will also record the stage of the security check whether it is input or output and the result of the security check whether it is allowed or blocked
    the result depends on whether the security pipeline returns a safe (true) bool to proceed or not
    """

    def record_security_check(
        self, stage: str, result: str
    ) -> None:
        """Record a security check."""
        SECURITY_CHECKS_TOTAL.labels(
            stage=stage, result=result
        ).inc()

    # ===================================
    # API
    # ===================================

    # This method is used to maniputlate the REQUESTS_TOTAL counter whenever we have a new API request and it will additionally record the method used, endpoint, and its status code, so we can have a better understanding of the API usage and performance.
    def record_request(self, method: str, endpoint: str, status: int) -> None:
        """Record a complete API request."""
        REQUESTS_TOTAL.labels(
            method=method, endpoint=endpoint, status=str(status)
        ).inc()

    # this method will be used to manipulate and increment the REQUEST_ERRORS_TOTAL counter whenever we have an error in the API request and it will additionally record the endpoint and the type of error, so we can have a better understanding of the API errors and their causes.
    def record_request_error(self, endpoint: str, error_type: str) -> None:
        """Record an API error."""
        REQUEST_ERRORS_TOTAL.labels(
            endpoint=endpoint, error_type=error_type
        ).inc()

    """
    This method is going to also manipulate the same counter REQUEST_LATENCY but the main difference is that this method will not calculate the duration of the request, it will just record the duration that is passed to it as an argument
    for example: 
    REQUEST_LATENCY.labels(
    method="POST",
    endpoint="/api/chat",
).observe(1.25)

    ===> tells Prometheus that the request took 1.25 seconds to complete, and Prometheus will record this value in the histogram for the specified method and endpoint.

    """

    def record_request_latency(
        self,
        method: str,
        endpoint: str,
        duration_seconds: float,
    ) -> None:
        """Record API request latency."""
        REQUEST_LATENCY.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration_seconds)

    # this contextmanager decorator will be used to measure the latency of the API request and it will automatically record the latency in the REQUEST_LATENCY histogram, so we can have a better understanding of the API performance and its response time.
    @contextmanager
    # Iterator means that this function will yield a value and then continue executing after the yield statement, which is useful for context managers that need to perform some setup and teardown actions around a block of code.
    def track_request_latency(self, method: str, endpoint: str) -> Iterator[None]:
        """Measure API request latency without breaking the API request."""
        # start the timer manullay and add it in try-except block to make sure that if Pormetheus fails to start the timer we can handle the error
        try:
            timer = REQUEST_LATENCY.labels(
                method=method, endpoint=endpoint).time()
            timer.__enter__()

        except Exception:
            logger.exception(
                "Failed to start Prometheus timer for API request latency."
            )
            timer = None

        # yield statement is used to pause the execution of the context manager and allow the code inside the with block to execute, and then resume the execution of the context manager after the with block is done.
        try:
            yield

        finally:
            # here we need to stop the timer in case there was no error in start of the timer => timer not None
            if timer is not None:
                # we need to also stop the timer inside the try-catch block to make sure that if Prometheus fails to stop the timer we can handle the error and not break the API request
                try:
                    timer.__exit__(None, None, None)
                except Exception:
                    logger.exception(
                        "Failed to record API request latency metric"
                    )
    """
    
    1- What is the concepet of with in python?
    Run some setup before this block, run the block, then perform cleanup afterward.
    with open("test.txt") as file:
        data = file.read()
    conceptually, OPEN FILE => READ FILE => CLOSE FILE
    so we dont manually write:
    
    file = open("test.txt")
    data = file.read()
    file.close()

    => The with statement handles the cleanup.
    
    
    2- What is a context manager in Python?
    A context manager is simply something that defines:
    "What should happen when we ENTER this block?"
    and:
    "What should happen when we EXIT this block?"
    
    for example: 
    with database_connection():
        query_database()
    
    ENTER => connect to database => query_database() => EXIT => close database connection
    
    @contextmanager
    def timer():
        print("START")
        yield
        print("END")
    
    output:
    START
    HELLO
    END
            
        
    3- What is Yield in Python?
    
    when we have this for example:
    def test():
        yield 10
        
    => not normal function anymore: it is a generator function
    so when we call for example: result = test() => python doesn't immediately execute the function, instead it returns a generator object that can be used to iterate over the values produced by the function.
    so when we call: next(result) => python will execute the function until it reaches the yield statement, and it will return the value 10, and it will pause the function's state at that point, so if we call next(result) again => python will resume the function's execution from where it left off, and it will continue until it reaches the next yield statement or the end of the function.
    
    def test():
        print("Before")
        yield 10
        print("After")
        yield 20
    
    x = test()
    next(x)
    
    Output:
    Before
    10
    
    next(x)
    
    Output:
    After
    20
    
    4- Now combine yield with context manager:
    @contextmanager
    def timer():
        print("START")

        yield

        print("END")
    The above is the function that we defined
    
    when we want to use it we can do the following:
    with timer():
        print("Do work")
    
    Python will organize it like the following: 
    timer() => print("START") => yield => PAUSE timer() => Python excutes: print("Do work") => timer() RESUMES => print("END")
    
    => Python, take this generator and treat the code before yield as ENTER logic and the code after yield as EXIT logic.
    
    now lets make this anology to the track_request_latency() function:
    
    @contextmanager => Make this function usable with with
    
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint,) => This selects the Prometheus histogram for: method = POST endpoint = /chat for example 
    
    what does .time means?
    it gives a a timer context manager that measures the time taken to execute the code block within the with statement and automatically records the duration in the histogram.
     
    ENTER => START TIMER => yield => YOUR API CODE => EXIT =>STOP TIMER => RECORD DURATION
    
    Now where does this API code actually run
    Suppose that somewhere in FastAPI application we have the following code:
    with metrics.track_request_latency("POST", "/chat"):
        response = process_request()
    The first thing is that python will enter this method which is track_request_latency() and inside this function we have with REQUEST_LATENCY.labels(...).time() so Prometheus will start the timer then it reaches yield 
    Which means Pause this function (timer) and go to the code inside the outer with statement which is: response = process_request() => python will execute this code and when it finishes it will go back to the track_request_latency() function and continue executing after the yield statement which is STOP TIMER and RECORD DURATION. 
    
    Note: even if there is nothing after the yield statement => it means that the function finishes:
    
    why we need the yield statement? because we need something that makes Python: Okay, setup is done (timer). Now let the actual code inside the with block execute.
    track_request_latency()

    4- What does Iterator mean?
    This is type hint which tells us that this is a generator function that yields values of type None. In this case, the function doesn't yield any values, but it still needs to be an iterator because it uses the yield statement to pause and resume execution.
    
    You're using yield because @contextmanager uses the point of the yield to separate setup from the code inside the with block and thats why we have Iterator[None] instead of having Iterator [float]
        
    """

    # ===================================
    # LLM
    # ===================================

    # this method will be used to manipulate and increment the LLM_REQUESTS_TOTAL counter whenever we have a new LLM request and it will additionally record the model used, so we can have a better understanding of the LLM usage and performance.
    def record_llm_request(self, model: str) -> None:
        """Record an LLM request."""

        LLM_REQUESTS_TOTAL.labels(
            model=model,
        ).inc()

    # this method will be used to manipulate and increment the LLM_ERRORS_TOTAL counter whenever we have an error in the LLM request and it will additionally record the model used and the type of error, so we can have a better understanding of the LLM errors and their causes.
    def record_llm_error(
        self,
        model: str,
        error_type: str,
    ) -> None:
        """Record an LLM error."""

        LLM_ERRORS_TOTAL.labels(
            model=model,
            error_type=error_type,
        ).inc()

    # this method will be used to manipulate the tokens in and out of the LLM and it will additionally record the model used, so we can have a better understanding of the LLM token usage and performance.
    def record_llm_tokens(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record LLM token usage."""

        if input_tokens > 0:
            LLM_INPUT_TOKENS_TOTAL.labels(
                model=model,
            ).inc(input_tokens)

        if output_tokens > 0:
            LLM_OUTPUT_TOKENS_TOTAL.labels(
                model=model,
            ).inc(output_tokens)

    @contextmanager
    def track_llm_latency(
        self,
        model: str,
    ) -> Iterator[None]:
        """
        Measure LLM request latency without breaking the LLM call.
        So, now if anything inside the Prometheus timing context itself fails. The exception will not bubble up and the outer node logic will not interpret it as an LLM failure.
        """
        try:
            # This creates the Prometheus timer object.
            timer = LLM_LATENCY.labels(
                model=model,
            ).time()

            # This is essentially what Python normally does automatically when you write: with timer -older version-
            """
            with timer:
                do_work()

            is conceptually equivalent to:
            timer.__enter__()
            do_work()
            timer.__exit__(...)
            
            now We are doing it manually because we want precise control over what happens when Prometheus fails.
            """

            timer.__enter__()

        except Exception:
            logger.exception(
                "Failed to start Prometheus timer for LLM latency."
            )
            timer = None
            # and then continue to the yield statement, so we can still execute the code inside the with block even if Prometheus fails to create the timer.
            # ===> response = primary_llm.invoke(...)
            # After the LLM finishes, execution returns after the yield.
            # we have

        try:
            yield

        finally:
            if timer is not None:
                try:
                    timer.__exit__(None, None, None)
                except Exception:
                    logger.exception(
                        "Failed to record LLM latency metric"
                    )
        """
        timer.__enter__()
            ↓
        START = 10:00:00.000

        yield
            ↓
        LLM runs

        timer.__exit__()
            ↓
        END = 10:00:01.500

        duration = 1.5 seconds
            ↓
        record 1.5 in Histogram
        """

    def record_token_limit_exceeded(
        self,
        limit_type: str,
    ) -> None:
        """Record a token limit exceeded event."""

        TOKEN_LIMIT_EXCEEDED_TOTAL.labels(
            limit_type=limit_type,
        ).inc()

    # ===================================
    # Cache
    # ===================================

    def record_cache_result(
        self,
        cache_type: str,
        result: str,
    ) -> None:
        """
        Record a cache lookup.

        cache_type:
            exact
            semantic

        result:
            hit
            miss
        """

        CACHE_REQUESTS_TOTAL.labels(
            cache_type=cache_type,
            result=result,
        ).inc()

    @contextmanager
    def track_cache_latency(
        self,
        cache_type: str,
        operation: str
    ) -> Iterator[None]:
        """Measure cache lookup latency."""

        try:
            timer = CACHE_LATENCY.labels(
                cache_type=cache_type,
                operation=operation,
            ).time()

            timer.__enter__()

        except Exception:
            logger.exception(
                "Failed to start Prometheus timer for cache latency."
            )
            timer = None

        try:
            yield

        finally:
            if timer is not None:
                try:
                    timer.__exit__(None, None, None)
                except Exception:
                    logger.exception(
                        "Failed to record cache latency metric."
                    )

    def record_cache_error(
        self,
        operation: str,
        error_type: str,
    ) -> None:
        """Record a cache error."""

        CACHE_ERRORS_TOTAL.labels(
            operation=operation,
            error_type=error_type,
        ).inc()

    # ===================================
    # RAG
    # ===================================

    def record_rag_request(self) -> None:
        """Record a RAG pipeline execution."""

        RAG_REQUESTS_TOTAL.inc()

    def record_rag_error(
        self,
        error_type: str,
    ) -> None:
        """Record a RAG pipeline error."""

        RAG_ERRORS_TOTAL.labels(
            error_type=error_type,
        ).inc()

    @contextmanager
    def track_rag_latency(self) -> Iterator[None]:
        """Measure RAG pipeline latency."""

        try:
            timer = RAG_LATENCY.time()

            timer.__enter__()

        except Exception:
            logger.exception(
                "Failed to start Prometheus timer for RAG latency."
            )
            timer = None

        try:
            yield

        finally:
            if timer is not None:
                try:
                    timer.__exit__(None, None, None)
                except Exception:
                    logger.exception(
                        "Failed to record RAG latency metric."
                    )

    def request_started(self) -> None:
        """Increment active request count."""

        ACTIVE_REQUESTS.inc()

    def request_finished(self) -> None:
        """Decrement active request count."""

        ACTIVE_REQUESTS.dec()

    def get_metrics_summary(self) -> dict:
        """Return a clean summary of the current application metrics."""

        def histogram_summary(histogram) -> dict:
            """
            Convert a Prometheus Histogram into a clean summary.

            Returns:
            - count
            - total_seconds
            - average_seconds
            """

            groups: dict[str, dict] = {}

            for sample in histogram.collect()[0].samples:

                # Ignore histogram buckets and created timestamp
                if not (
                    sample.name.endswith("_count")
                    or sample.name.endswith("_sum")
                ):
                    continue

                labels = dict(sample.labels)

                # Remove bucket label if present
                labels.pop("le", None)

                key = str(labels)

                if key not in groups:
                    groups[key] = {
                        "count": 0,
                        "total_seconds": 0.0,
                        "average_seconds": 0.0,
                    }

                if sample.name.endswith("_count"):
                    groups[key]["count"] = int(sample.value)

                elif sample.name.endswith("_sum"):
                    groups[key]["total_seconds"] = sample.value

            # Calculate averages
            for values in groups.values():
                if values["count"] > 0:
                    values["average_seconds"] = (
                        values["total_seconds"]
                        / values["count"]
                    )

            return groups

        return {

            # =========================
            # Security
            # =========================
            "security": {
                "checks": {
                    str(sample.labels): sample.value
                    for sample in SECURITY_CHECKS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },
            },

            # =========================
            # API
            # =========================
            "api": {
                "requests": {
                    str(sample.labels): sample.value
                    for sample in REQUESTS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "errors": {
                    str(sample.labels): sample.value
                    for sample in REQUEST_ERRORS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "latency": histogram_summary(
                    REQUEST_LATENCY
                ),
            },

            # =========================
            # LLM
            # =========================
            "llm": {
                "requests": {
                    str(sample.labels): sample.value
                    for sample in LLM_REQUESTS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "errors": {
                    str(sample.labels): sample.value
                    for sample in LLM_ERRORS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "input_tokens": {
                    str(sample.labels): sample.value
                    for sample in LLM_INPUT_TOKENS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "output_tokens": {
                    str(sample.labels): sample.value
                    for sample in LLM_OUTPUT_TOKENS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "token_limit_exceeded": {
                    str(sample.labels): sample.value
                    for sample in TOKEN_LIMIT_EXCEEDED_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "latency": histogram_summary(
                    LLM_LATENCY
                ),
            },

            # =========================
            # Cache
            # =========================
            "cache": {
                "requests": {
                    str(sample.labels): sample.value
                    for sample in CACHE_REQUESTS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "errors": {
                    str(sample.labels): sample.value
                    for sample in CACHE_ERRORS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "latency": histogram_summary(
                    CACHE_LATENCY
                ),
            },

            # =========================
            # RAG
            # =========================
            "rag": {
                "requests": (
                    RAG_REQUESTS_TOTAL
                    .collect()[0]
                    .samples[0]
                    .value
                ),

                "errors": {
                    str(sample.labels): sample.value
                    for sample in RAG_ERRORS_TOTAL.collect()[0].samples
                    if sample.name.endswith("_total")
                },

                "latency": histogram_summary(
                    RAG_LATENCY
                ),
            },

            # =========================
            # Active requests
            # =========================
            "active_requests": (
                ACTIVE_REQUESTS
                .collect()[0]
                .samples[0]
                .value
            ),
        }


# One shared collector used throughout the application.
# since we want to use the same instance of the MetricsCollector class throughout the application, we create a single instance of it and assign it to the variable metrics
# this way, any part of the application that needs to record metrics can import this instance and use it to update the metrics, ensuring that all metrics are collected in a consistent manner.
metrics = MetricsCollector()

"""
FastAPI
   │
   ├── metrics.record_request()
   ├── metrics.track_request_latency()
   │
   ▼
Security
   │
   ▼
Cache Manager
   │
   ├── exact → hit/miss
   ├── semantic → hit/miss
   └── latency
   │
   ▼
RAG
   │
   ├── request count
   └── latency
   │
   ▼
LLM
   │
   ├── request count
   ├── latency
   ├── errors
   └── tokens

"""


# class MetricsCollector:
#     """Collects and aggregates application metrics.

#     In production, replace the with Promethus client:
#     from prometheus_client import Counter, Histogram

#     """

#     def __init__(self) -> None:
#         self._request_total = 0
#         self._errors_total = 0
#         self._latency_sum = 0.0
#         self._latency_count = 0
#         self._tokens_total = 0
#         self.tokens_output = 0
#         self.cache_hits = 0
#         self.cache_misses = 0

#     def record_request(
#         self,
#         latency_ms: float,
#         input_tokens: int,
#         output_tokens: int,
#         error: bool = False,
#         cache_hit: bool = False,

#     ):
#         """Record a request and update metrics."""
#         self._request_total += 1
#         if error:
#             self._errors_total += 1
#         self._latency_sum += latency_ms
#         self._latency_count += 1
#         self._tokens_total += input_tokens + output_tokens
#         self.tokens_output += output_tokens
#         if cache_hit:
#             self.cache_hits += 1
#         else:
#             self.cache_misses += 1

#     @property
#     def summary(self) -> dict:
#         """Return a summary of the collected metrics."""
#         avg_latency = (
#             self._latency_sum / self._latency_count
#             if self._latency_count > 0
#             else 0.0
#         )
#         error_rate = (
#             self._errors_total / self._request_total
#             if self._request_total > 0
#             else 0.0
#         )

#         cache_total = self.cache_hits + self.cache_misses
#         cache_hit_rate = (
#             self.cache_hits / cache_total
#             if cache_total > 0
#             else 0.0
#         )

#         return {
#             "total_requests": self._request_total,
#             "total_errors": self._errors_total,
#             "error_rate": error_rate,
#             "average_latency_ms": avg_latency,
#             "total_tokens": self._tokens_total,
#             "total_output_tokens": self.tokens_output,
#             "cache_hits": self.cache_hits,
#             "cache_misses": self.cache_misses,
#             "cache_hit_rate": cache_hit_rate,

#         }
