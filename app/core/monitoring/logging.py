"""
Now in the monitoring what we are going to build is structured json logger: Which can be used in production to send logs toAWS CloudWatch, Azure Monitor, Datadog, Elasticsearch/Kibana, Grafana/Loki

1- First lets understand what logger is: Logger is application's recording system that allow us to record events, errors, and other information during the execution of the application. It helps in debugging, monitoring, and analyzing the behavior of the application.

For example: API recieves "What is RAG?"

Then the application is going to perform the following steps:
1- security_check_input
2- cache_lookup
3- RAG retrieval
4- LLM call
5- cache_store
6- security_check_output

At each point what we can do is 
INFO -> Request received: "What is RAG?"
INFO -> Security check input passed
INFO -> Cache lookup completed

INFO -> LLM call completed
INFO -> Cache store completed
INFO -> Security check output passed

Those records are called logs

2- Why JSON? 
since normal log might look like this: 2026-08-16 16:01:52 INFO LLM request completed
while JSON log might look like this:
{
    "timestamp": "2026-08-16T16:01:52+00:00",
    "level": "INFO",
    "message": "LLM request completed",
    "logger": "production-api",
    "module": "agent",
    "function": "invoke",
    "line_no": 190,
    "latency_ms": 1250,
    "input_tokens": 100,
    "output_tokens": 250
}
and JSON one is much easier for monitoring systems to process and analyze, and it can be easily queried and filtered based on different fields.
for example, we can query all the logs that have level ERROR or all the logs that have a specific function name or module name

3- What is logging?
In Python we already have a built-in logging module: import logging
It provides set of standard logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

for example, logger.info("Request received: What is RAG?") or logger.error("LLM request failed: Timeout error")

4- What is JsonFormatter?
JsonFormatter is a custom formatter for the Python logging module that formats log records as JSON objects. This allows for structured logging, making it easier to parse and analyze logs in monitoring systems.
so, Python's logging system normally needs a formatter to determine how a log should look.
thats why we have def(self, record: logging.LogRecord)

5- What is record?
it is a LogRecord instance that contains all the information about the log event, such as the message, level, timestamp, module, function, line number, and any additional data.
=> thats why we can access record.levelname, record.getMessage(), record.name, record.module, record.funcName, record.lineno, and getattr(record, "extra_data", None)

6- we have the "message": record.getMessage() which is the actual log message that we want to record
so when we call logger.info("Request received: What is RAG?") => the message will be "Request received: What is RAG?"

7-This is the most important part which is the extra_data: this allow us to add structured information 
for example: logger.info(
    "LLM request completed",
    extra={
        "extra_data": {
            "latency_ms": 1250,
            "input_tokens": 100,
            "output_tokens": 250,
        }
    }
)

8- What is get_logger(name: str = "production-api") -> logging.Logger:
This function creates and returns a structured JSON logger with the specified name. It sets the logging level to INFO and adds a console handler that outputs logs in JSON format using the JsonFormatter. The logger can be used throughout the application to log events, errors, and other information in a structured manner.

9- What is the handler = logging.StreamHandler(sys.stdout):
This line determines where the log messages will be sent. In this case, it sends the logs to the standard output (console) using sys.stdout. This is useful for development and debugging, as you can see the logs directly in the console.
While for production, you might want to send the logs to a file or a log aggregation service like AWS CloudWatch, Azure Monitor, Datadog, Elasticsearch/Kibana, Grafana/Loki, etc.

Finally, how the logger is going to be used in the application: 
for example, in the cache_manager.py file, we can use the logger to log cache hits and misses:
from app.core.monitoring.logger import get_logger

logger = get_logger(__name__)

logger.info(
    "Cache hit",
    extra={
        "extra_data": {
            "cache_type": "exact",
            "query": query
        }
    }
)

or in the security pipeline, we can log security check results:
logger.warning(
    "Prompt injection detected",
    extra={
        "extra_data": {
            "security_type": "prompt_injection"
        }
    }
)

or in the LLM call, we can log the latency and token usage:
logger.info(
    "LLM request completed",
    extra={
        "extra_data": {
            "latency_ms": 1250,
            "input_tokens": 100,
            "output_tokens": 250
        }
    }
)

                    FastAPI
                       │
                       ▼
                 Security Pipeline
                       │
                       ▼
                  Cache Manager
                  /           \
          Exact Cache      Semantic Cache
                  \           /
                       │
                    Cache Miss
                       │
                       ▼
                  RAG Pipeline
                       │
                       ▼
                     LLM
                       │
                       ▼
               Output Validation
                       │
                       ▼
                    Response


Monitoring exists across the entire pipeline:

        ┌───────────────────────────────┐
        │        Structured Logger      │
        │                               │
        │ Security / Cache / RAG / LLM  │
        └───────────────────────────────┘

        ┌───────────────────────────────┐
        │        Metrics Collector      │
        │                               │
        │ latency / errors / tokens     │
        │ cache hits / requests         │
        └───────────────────────────────┘

"""

# this below is used to allow us to have structured logging in the monitoring and logging for production
import logging

# this below is used to allow us to convert python dictionaries into JSON format
# data = {"name": "Ibrahim", "age": 25}
# json.dumps(data)
# {"name": "Ibrahim", "age": 25}
import json
from datetime import datetime, timezone
import sys
from app.core.config import get_settings
from pathlib import Path
from logging.handlers import RotatingFileHandler


# first we need to create the custom json formatter for the logger
class JsonFormatter(logging.Formatter):
    """Format log records as JSON for log aggregation (ELK, Datadog, etc.)."""

    # this method will format the log record into a JSON object with the timestamp, level, message, module, function, and line number. It will also include any extra data passed to the log record.
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line_no": record.lineno,
        }

        # Add application-specific structured data
        extra_data = getattr(record, "extra_data", None)

        # Merge any extra data attached to the record (e.g., from `extra` parameter in logging calls)
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)
        return json.dumps(log_obj)


def get_logger(name: str = "production-api") -> logging.Logger:
    """Create a structured JSON logger."""
    settings = get_settings()

    # this will create a logger with the specified name and set the logging level to INFO. It will also add a console handler that outputs logs in JSON format using the JsonFormatter.
    logger = logging.getLogger(name)

    logger.setLevel(settings.log_level)

    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )

        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

    return logger

# the above will generate machine readable logs which we can use to send to lang graph
# this is totally differnet and better than having text
# every line log is a JSON obeject => tools like data log, elastic search or cloud watch and many other can inges this directly
# so we can query later on for example all the logs that have level ERROR or all the logs that have a specific function name or module name
