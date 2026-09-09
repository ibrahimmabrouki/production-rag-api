"""
ChatService is the orchestrator
It is eventually responsible for:
Request => Security Chcek => Token budget check => Cache lookup => Cache hit?
If cache hit => Return
If cache miss => RAG => LLM (Agent) => Output validation => Cache response => Return

ChatService
    │
    ├── SecurityPipeline
    │
    ├── CacheManager
    │
    ├── RAG/Agent
    │
    ├── Output validation
    │
    └── Metrics

Request
   ↓
Security
   ↓
Cache lookup
   ↓
 ┌───────────────┐
 │ Cache hit?    │
 └───────┬───────┘
     yes │ no
         │
    return       RAG
                  ↓
                LLM
                  ↓
            Output security
                  ↓
             Cache response
                  ↓
               Return


"""
import asyncio
from app.core.security.pipeline import SecurityPipeline
from app.core.cache.cache_manager import CacheManager
from app.agents.agent import ProductionAgent
from app.core.monitoring.metrics import metrics
from app.core.monitoring.logging import get_logger
from app.core.token_budget.budget import TokenBudget
from app.core.token_budget.usage_repository import ChatUsageRepository

from app.agents.response_normalizer import normalize_agent_response

"""
Here are some important notes to take into consideration to understand how things work in this important chat service:
1- The first thing which is understanding what FastAPI is and how it works:
In general it is a Python framework for building APIs. so if the application is running in http://localhost:8000 and a client sends a POST /api/chat -which is HTTP request- with a JOSN body. { "message": "What is RAG?"} FastAPI will recieve the HTTP request and -it will route it to the correct endpoint so in this way it will figure out the Python function to handle the client request- then it converts back the result into HTTP response.
so, client (HTTP request) => FastAPI (Finds correct route) => Python function (Business logic) => FastAPI (Convert to HTTP response) => Client (HTTP response)

Now the Important thing is why FASTAPI is asynchronous?
-since the web server is supposed to handle multiple requests at the same time: User A → asks a question, User B → asks a question, User C → asks a question
and some of the work involves waiting such as Redis request, Database request, LLM API request, HTTP API request and many others. => during the waiting time CPU is not doing anything
Send Redis request
       ↓
   ..........
   waiting
   ..........
       ↓
Redis response
Asynchronous programming lets Python use that waiting time to work on another request.



Some important notes:
2- Synchronous vs Asynchronous:
- Synchronous code means: Do this operation and don't continue until it is done: task_a() => finish A => task_b() => finish B

- Asynchronous code means: Start this operation and continue with other operations while it's running.

Asynchronous programming is useful when an operation spends time waiting for external I/O
for example, when Python talks to redis => (waiting for redis to respond)

so, instead of blocking the whole application while redis is responding, asynchronous code allows the event to work on another request during the waiting time.

but the important distiction is that async does NOT automatically make a function run in parallel or make it faster.
=> its important benefits appear when a function reaches an operations that can be awaited such as: Redis request, Database request, LLM API

2- What does await mean?
we can think of await as a way to tell Python: "Pause this function here, let other things run, and come back when the awaited operation is done."

so for example if we have a function that looks like this:
response = await redis.get("key")

in plain english it means: start this function which is asynchronous, i need the result before continuing the function. while we are waiting for the result, let the event loop -which is responsible for managing the FastAPI event loop handle other requests.- handle other requests
and when the redis responds, the event loop will come back to this function and continue executing it.

Note: The thing coordinating asynchronous tasks is called the event loop.

so instead of:
Request A
   ↓
Redis request
   ↓
BLOCK EVERYTHING
   ↓
10 ms
   ↓
Redis response

asyn FastAPI allows us to do this:
Request A
   ↓
await Redis
   │
   │ waiting
   │
   ├──────────────→ Request B can run
   │
   ├──────────────→ Request C can run
   │
   ↓
Redis responds
   ↓
Continue Request A


- Start Request A => A waits for Redis => Switch to B => B waits for database => Switch to C => C performs some work => Redis returns for A => Continue A => Database returns for B => Continue B

this is only done when we have external I/O operations that can be awaited but incase it is a synchronous operation such as SecurityPipeline.check_input()
we dont need to await since it is synchronous and fast

def function()
    ↓
call normally

async def function()
    ↓
usually await it from async code

3- What happens if we call an asynchronous function without await?
we will get a coroutine object instead of the result.

but await can be normally used only inside an async function, so if we have synchronous function and we want to call await then it is not valid since normal synchronous functions does not participate in the event loop.

4- Now the important problem which is Blocking code:
assume that we are inside the async def process() function and we have some synchronous code that takes a long time:
for example, result = slow_sync_function() takes 10 seconds to respond => if this blocks the event loop then we will have a problem.
Event loop => slow_sync_function() => BLOCKED => 10 seconds => returns

3- What is a thread?
A thread is a separate execution path within the same Python process.

Python Process
│
├── Thread 1
├── Thread 2
├── Thread 3
└── Thread 4

              FastAPI process
                    │
              Event-loop thread
                    │
       ┌────────────┼────────────┐
       ↓            ↓            ↓
   Request A    Request B    Request C

we want to avoid blocking the event-loop thread sit blocked for a long time.
Now, suppose that we have a long-running operation: for example the production agent below is synchronous blocking operation
Event loop => agent => LLM => 10 seconds to respond (Blocked) => continue

now why to use threads?
since def invoke(self, message: str) is synchronous internally such as primary_llm.invoke(...)
and this is the important combination:
FastAPI async code
        ↓
ChatService.process()
        ↓
SLOW SYNCHRONOUS operation
        ↓
ProductionAgent.invoke()

we can't do await self.agent.invoke(message) because it is synchronous, so we need to run it in a separate thread to avoid blocking the event-loop thread.

so, we use:

agent_result = await asyncio.to_thread(
    self.agent.invoke,
    cleaned_message,
)

This is synchronous blocking work. Run it on another worker thread so that it doesn't block the event-loop thread.

why do we still use await?
since we have result = await asyncio.to_thread(...) which means the work is running on another thread but ChatService still needs the result before it can continue
for example, it can't do check_output(response) until the agent has actually the response => we need to await for the result other wise we will get a coroutine object

so, await asyncio.to_thread(...): Run this synchronous operation on another thread. Suspend this coroutine until that thread finishes, while allowing the event loop to work on other tasks.
"""

# in this line we are passing the name of the current module to the get_logger function so that it can create a Logger object with the name of the current module
logger = get_logger(__name__)


class ChatService:
    """
    Orchestrates the chat request workflow.

    The service does not create its own dependencies.
    They are provided by the application layer.

    """
    """
    In the below function we dont need to instantiate the MetricsCollector class since we already have a single instance of the MetricsCollector class which is metrics = MetricsCollector() in app/core/monitoring/metrics.py
    ===> in the ChatService class we can directly use the metrics instance to record metrics without reinstantiating it
    """

    def __init__(
        self,
        security_pipeline: SecurityPipeline,
        cache_manager: CacheManager,
        agent: ProductionAgent,
        token_budget: TokenBudget,
        chat_usage_repository: ChatUsageRepository,


    ) -> None:
        self.security_pipeline = security_pipeline
        self.cache_manager = cache_manager
        self.agent = agent
        self.token_budget = token_budget
        self.chat_usage_repository = chat_usage_repository

    async def process(self, message: str, thread_id: str) -> dict:
        """
        Process a user message through:

        1. Input security
        2. Cache lookup
        3. Agent execution on cache miss
        4. Normalize agent response
        5. Output security
        6. Cache storage
        7. Return response
        """

        # ============================================================
        # REQUEST START
        # ============================================================

        # This is the very beginning of the process method then we need to log that the Request has been started
        logger.info("Chat request started", extra={"extra_data": {
                    "thread_id": thread_id, }})

        # ============================================================
        # 1. INPUT SECURITY
        # ============================================================
        try:
            # SecurityPipeline.check_input() is synchronous and fast,
            # so we call it normally without await.
            is_input_safe, cleaned_message, input_security_notes = (
                self.security_pipeline.check_input(message)
            )

            """
            Here we are using the metrics instance (which is a singleton) to record the result of the input security check.
            in addition to increment the counter SECURITY_CHECKS_TOTAL
            
            but there is one case which could happen and we should take it into consideration which is an exception could be raised during the recording of the metrics and it is located inside the same try block 
            where the SecurityPipeline.check_input(message) is called, so if an exception is raised during the recording of the metrics, it will be caught by the except block and it will log the exception and return a failure to the client since we don't have the result of the input security check.
            so what we can do is excuting the metrics.record_security_check(...) in a separate try-except block so that if an exception is raised during the recording of the metrics, it will be caught by the except block and it will log the exception but it will not return a failure to the client since we have the result of the input security check.
            """

            try:
                metrics.record_security_check(
                    stage="input",
                    result="allowed" if is_input_safe else "blocked",
                )
            except Exception:
                logger.exception(
                    "Failed to record input security metric",
                    extra={"extra_data": {"thread_id": thread_id}},
                )

        except Exception:
            logger.exception(
                "Input security check failed", extra={"extra_data": {
                    "thread_id": thread_id, }
                })

            return {
                "success": False,
                "response": None,
                "cleaned_message": None,
                "input_security_notes": None,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": None,
                "error": "Input security check failed.",
            }

        # here we want to log that the input security check has been completed and the result of the check passed all the security Pipeline
        logger.info(
            "Input security check completed",
            extra={
                "extra_data": {
                    "thread_id": thread_id,
                    "is_safe": is_input_safe,
                    "security_notes_count": len(input_security_notes),
                }
            },
        )

        # If prompt injection or another blocking security issue
        # is detected, stop processing immediately.
        if not is_input_safe:
            # in case the security checks detected something unusual in the input it will return unsafe then we need to log that
            # security check has blocked the request becuase the input message failed to pass the security checks
            logger.warning("Input security check blocked request", extra={"extra_data": {
                "thread_id": thread_id, "input_security_notes_count": len(input_security_notes), "reason": "Input message failed security checks.", }})
            return {
                "success": False,
                "response": None,
                "cleaned_message": None,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": None,
                "error": "Input message failed security checks.",
            }

        # ============================================================
        # 2. PER-REQUEST TOKEN BUDGET
        # ============================================================

        # This will act as the first layer of defense against token budget exhaustion and violation of the rules and policies.
        # first we need to check that the input message is within the allowed token budget limit for this specific conversation/thread.
        allowed, estimated_input_tokens = (
            self.token_budget.check_input(cleaned_message)
        )

        # here we need to log that the cleaned message which is the result of the input security check has been checked against the token budget and whether it is allowed or not and how many tokens are estimated for this cleaned message
        logger.info("Token budget check completed", extra={"extra_data": {
                    "thread_id": thread_id, "allowed": allowed, "estimated_input_tokens": estimated_input_tokens, }})

        if not allowed:
            # if the input message is not allowed, we need to log that the input token budget check has blocked the request
            logger.warning("Token budget check blocked request", extra={"extra_data": {
                "thread_id": thread_id, "estimated_input_tokens": estimated_input_tokens, "reason": ("Maximum input token limit exceeded."), }})

            """
            After the input token check there is some metric that we need to record which is incase of the input exceeded the allowed token budget limit for a single request message we need to increment the TOKEN_LIMIT_EXCEEDED_TOTAL counter and the limit_type
            """
            try:
                metrics.record_token_limit_exceeded(
                    limit_type="input_tokens",
                )
            except Exception:
                logger.exception(
                    "Failed to record token limit exceeded metric",
                    extra={"extra_data": {"thread_id": thread_id}},
                )

            return {
                "success": False,
                "response": None,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": None,
                "error": "Maximum input token limit exceeded.",
            }

        # ============================================================
        # 3. CHAT TOKEN BUDGET - LAYER 1
        # ============================================================

        try:
            # The second step in the first layer of defense is to check the total usage of the conversation/thread and see if it is within the allowed token budget limit for this specific conversation/thread.
            # first we need to get the current usage of the conversation/thread from the redis
            usage = await self.chat_usage_repository.get_usage(
                thread_id
            )

        except Exception:
            # in case we have an exception while getting the current usage of the conversation/thread from the redis we will log that and return a failure to the client since we don't have the current usage of the conversation/thread
            logger.exception(
                "Failed to load chat usage",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                    }
                },
            )

            return {
                "success": False,
                "response": None,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": None,
                "error": "Failed to load chat usage.",
            }

        allowed, reason = self.token_budget.check_chat(
            usage=usage,
            estimated_input_tokens=estimated_input_tokens,
        )

        # here we need to log that the cleaned message is checked against the chat usage and whether it is allowed or not and how many tokens are estimated for this cleaned message and what is the current usage of the conversation/thread
        logger.info("Chat usage budget check completed", extra={"extra_data": {
                    "thread_id": thread_id, "allowed": allowed, "estimated_input_tokens": estimated_input_tokens, "total_requests": usage.total_requests, "total_input_tokens": usage.total_input_tokens, "total_output_tokens": usage.total_output_tokens, "reason": f"Token budget layer 1 check: {reason}", }})

        if not allowed:
            # if the total usage of the conversation/thread is not allowed, we need to log that the chat usage check has blocked the request alongside the returned reason
            logger.warning("Chat usage check blocked request", extra={"extra_data": {
                "thread_id": thread_id, "allowed": allowed, "estimated_input_tokens": estimated_input_tokens, "reason": f"Token budget layer 1 failed: {reason}", }})

            """
            After the chat usage check there is some metric that we need to record which is incase of the usage exceeded the allowed token limit and request count exceeded for a single conversation/thread, we need to increment the TOKEN_LIMIT_EXCEEDED_TOTAL counter and the limit_type chat_usage
            since the check_chat() method is responsible for checking both the total token usage and the total request count for a single conversation/thread, we can use the same the same limit_type which is chat_usage
            """

            try:
                metrics.record_token_limit_exceeded(
                    limit_type="chat_usage",
                )
            except Exception:
                logger.exception(
                    "Failed to record token limit exceeded metric",
                    extra={"extra_data": {"thread_id": thread_id}},
                )

            return {
                "success": False,
                "response": None,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": None,
                "error": f"Token budget layer 1 failed: {reason}",
            }

        # ============================================================
        # 4. CHAT TOKEN BUDGET - ATOMIC LAYER 2
        # ============================================================

        try:
            # then we need to reserve the request for this specific conversation/thread and check if it is within the allowed token budget limit
            # but this time we need to make the read and write operation to the redis atomic against the concurrent requests happening from different workers
            allowed, reason = await self.chat_usage_repository.reserve_request(
                chat_id=thread_id,
                estimated_input_tokens=estimated_input_tokens,
                max_chat_tokens=self.token_budget.max_chat_tokens,
                max_requests_per_chat=self.token_budget.max_requests_per_chat,
            )

        except Exception as e:
            logger.exception(
                "Failed to reserve request",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                    }
                },
            )

            return {
                "success": False,
                "response": None,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": None,
                "error": f"Failed to reserve request: {str(e)}",
            }

        # here we need to log that the request has been reserved for this specific conversation/thread and whether it is allowed or not and what is the reason for the decision
        logger.info("Request reservation completed", extra={"extra_data": {
                    "thread_id": thread_id, "allowed": allowed, "estimated_input_tokens": estimated_input_tokens, "max_chat_tokens": self.token_budget.max_chat_tokens, "max_requests_per_chat": self.token_budget.max_requests_per_chat, "reason": f"Token budget layer 2 check: {reason}", }})

        if not allowed:
            # if the request reservation is not allowed, we need to log that the request reservation has blocked the request alongside the returned reason
            logger.warning("Request reservation blocked request", extra={"extra_data": {
                "thread_id": thread_id, "allowed": allowed, "estimated_input_tokens": estimated_input_tokens, "max_chat_tokens": self.token_budget.max_chat_tokens, "max_requests_per_chat": self.token_budget.max_requests_per_chat, "reason": f"Token budget layer 2 failed: {reason}", }})
            """
            After the chat usage check there is some metric that we need to record which is incase of the usage exceeded the allowed token limit and request count exceeded for a single conversation/thread, we need to increment the TOKEN_LIMIT_EXCEEDED_TOTAL counter and the limit_type chat_usage
            since the check_chat() method is responsible for checking both the total token usage and the total request count for a single conversation/thread, we can use the same the same limit_type which is chat_usage
            """

            try:
                metrics.record_token_limit_exceeded(
                    limit_type="chat_usage",
                )
            except Exception:
                logger.exception(
                    "Failed to record token limit exceeded metric",
                    extra={"extra_data": {"thread_id": thread_id}},
                )
            return {
                "success": False,
                "response": None,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": None,
                "error": f"Token budget layer 2 failed: {reason}",
            }

        """
        Input security
        ↓
        Per-request token check
        ↓
        Load usage from Redis
        ↓
        Layer 1: TokenBudget.check_chat()
        ↓
        Layer 2: reserve_request()
        ↓
        Cache lookup
        """

        # ============================================================
        # 5. CACHE LOOKUP
        # ============================================================

        # CacheManager.get() is asynchronous because it communicates
        # with Redis.
        # in some cases the cache loopup through the cache_manager.get() might fail and raise an exception so we need to add exception handling here
        # but incase of the failure we will not return a failure to the client since we have the other option which is to call the agent and get the response from it
        # so, we will just log the error and continue to call the agent to get the response
        """
        so, in the exception:
        cache works + hit → return cached response
        cache works + miss → call agent
        cache fails → treat as miss → call agent
        """

        try:
            is_cached, _, cached_response, cache_type = await self.cache_manager.get(
                cleaned_message
            )
            # here we need to log that the cache lookup has been completed and whether it is a cache hit or miss and what is the cache type if it is a cache hit
            logger.info("Cache lookup completed", extra={"extra_data": {
                "thread_id": thread_id, "is_cached": is_cached, "cache_type": cache_type, }})

        except Exception as e:
            # Cache is fail-open:
            # continue to the agent instead of failing the request.
            logger.exception("Cache lookup failed", extra={"extra_data": {
                "thread_id": thread_id, "fallback_action": "Call agent", "error": str(e), "reason": "Cache lookup failed, treating as cache miss.", }})

            is_cached = False
            cached_response = None
            cache_type = None

        # ============================================================
        # 6. CACHE HIT
        # ============================================================

        if is_cached:

            # In case of the cache hit we need to update the usage of the conversation/thread in the redis to reflect the new usage
            output_tokens = self.token_budget.estimate_tokens(
                cached_response
            )

            # here we need to log that the cache hit has been successful and we will return the cached response to the client
            logger.info(
                "Chat response served from cache",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "cache_type": cache_type,
                        "estimated_output_tokens": output_tokens,
                    }
                },
            )

            """
            In some cases the record_output_usage might fail and raise an exception so we need to add exception handling here
            but incase of the failure we will not return a failure to the client since we have the cached response and we can return it to the client.
            so, we will just log the error and return the cached response to the client.
            """
            try:
                await self.chat_usage_repository.record_output_usage(
                    thread_id,
                    output_tokens=output_tokens,
                )

                # here we need to log that the usage of the conversation/thread has been updated in the redis to reflect the new usage after the cache hit and estimated output tokens for the cached response
                logger.info(
                    "Output token usage recorded",
                    extra={
                        "extra_data": {
                            "thread_id": thread_id,
                            "source": "cache",
                            "output_tokens": output_tokens,
                        }
                    },
                )

            except Exception:
                # Response is already available.
                # Usage failure should not break the request.
                # We will just log the error and continue to return the cached response to the client.

                logger.exception("Failed to update chat usage after cache hit", extra={"extra_data": {
                    "thread_id": thread_id, "output_tokens": output_tokens, "error": "Failed to update chat usage after cache hit.", }})
                pass

            # here we need to log that the request has been completed successfully and we will return the cached response to the client
            logger.info(
                "Chat request completed",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "success": True,
                        "cached": True,
                        "cache_type": cache_type,
                        "estimated_input_tokens": (
                            estimated_input_tokens
                        ),
                        "estimated_output_tokens": output_tokens,
                    }
                },
            )

            return {
                "success": True,
                "response": cached_response,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": True,
                "cache_type": cache_type,
                "model_used": None,
                "error": None,
            }

        # ============================================================
        # 7. CACHE MISS → AGENT
        # ============================================================

        # ProductionAgent.invoke() is currently synchronous.

        # Since the ChatService runs inside an async FastAPI request,
        # we execute the blocking synchronous Agent call in a worker
        # thread so that it does not block FastAPI's event loop.
        # we need to add the below code in try-catch block since sometimes the invoke actually fails and raises an exception before even reaching agent_result.get("error")

        logger.info(
            "Agent invocation started",
            extra={
                "extra_data": {
                    "thread_id": thread_id,
                }
            },
        )

        try:
            agent_result = await asyncio.to_thread(
                self.agent.invoke,
                cleaned_message,
            )

        except Exception as exc:
            # in case there is an error and lead to exception during the execution of the agent we will log that and return a failure to the client since we don't have a response from the agent

            logger.exception(
                "Agent invocation failed",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "error_type": type(exc).__name__,
                    }
                },
            )

            return {
                "success": False,
                "response": None,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": None,
                "error": f"Agent invocation failed: {str(exc)}",
            }

        """
        after calling the agent and getting back the response we need to check whether the agent succeeded or failed to generate a repsonse
        we know that the agent might fail in the primary mode (after the desired number of attempts we specify in the settings), and then might fail in the in fallback mode
        so based on the nodes file in app/agents/nodes.py we can see that incase of failure the methods are going to return an error field and incase of success the error field is going to be None and the response field is going to contain the response generated by the agent
        so we can check if the error field is None or not.

        Agent invoked
            ↓
            Check agent_result["error"]
            ├── error → return failure immediately
            └── no error → normalize response
                            ↓
                        output security
                            ↓
                        record tokens
                            ↓
                        cache response
        """

        # ============================================================
        # 8. AGENT RESULT VALIDATION
        # ============================================================

        agent_error = agent_result.get("error")

        if agent_error:
            # incase the invoke of the agent is successful but the agent failed to generate a response we will log that and return a failure to the client since we don't have a response from the agent
            logger.error(
                "Agent failed to generate response",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "model_used": agent_result.get(
                            "model_used"
                        ),
                        "agent_error": str(agent_error),
                    }
                },
            )

            return {
                "success": False,
                "response": agent_result.get("response"),
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": agent_result.get("model_used"),
                "error": f"Agent failed to generate a response: {agent_error}",

            }

        model_used = agent_result.get("model_used")

        # here after the agent invocation is successfull and the agent did not fail to generate a response we will log that the agent invocation is completed successfully and we have a response from the agent
        logger.info(
            "Agent invocation completed",
            extra={
                "extra_data": {
                    "thread_id": thread_id,
                    "model_used": model_used,
                }
            },
        )

        # ============================================================
        # 9. RESPONSE NORMALIZATION + OUTPUT SECURITY
        # ============================================================

        # we need to add exception handling here since the normalize_agent_response and output security checks might fail in some cases and raise an exception
        try:
            response = normalize_agent_response(agent_result["response"])

            logger.info(
                "Agent response normalized",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "model_used": model_used,
                    }
                },
            )

            # Validate/mask the generated response before returning it
            # to the client or storing it in Redis.
            cleaned_response, output_security_notes, is_output_safe = (
                self.security_pipeline.check_output(response)
            )

            """
            we also need to use the metric here to record the result of the output security check and increment the counter SECURITY_CHECKS_TOTAL
            """

            try:
                metrics.record_security_check(
                    stage="output",
                    result="safe" if is_output_safe else "blocked",
                )
            except Exception:
                logger.exception(
                    "Failed to record output security metric",
                    extra={"extra_data": {"thread_id": thread_id}},
                )

            logger.info(
                "Output security check completed",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "model_used": model_used,
                        "security_notes_count": len(
                            output_security_notes
                        ),
                    }
                },
            )

        except (KeyError, TypeError, ValueError) as exc:
            # in case the normalize_agent_response or the output security checks failed and raised an exception we will log that and return a failure to the client since we don't have a valid response from the agent
            logger.exception(
                "Failed to process agent response",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "model_used": model_used,
                        "error_type": type(exc).__name__,
                    }
                },
            )

            return {
                "success": False,
                "response": None,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": agent_result.get("model_used"),
                "error": f"Failed to process agent response: {str(exc)}",
            }

        except Exception as exc:

            logger.exception(
                "Output security processing failed",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "model_used": model_used,
                        "error_type": type(exc).__name__,
                    }
                },
            )

            return {
                "success": False,
                "response": None,
                "cleaned_message": cleaned_message,
                "input_security_notes": input_security_notes,
                "output_security_notes": [],
                "cached": False,
                "cache_type": None,
                "model_used": model_used,
                "error": "Output security processing failed.",
            }

        # ============================================================
        # 10. OUTPUT TOKEN USAGE
        # ============================================================

        """
        In this case after calling the agent and getting back the response we need to update the usage of the conversation/thread in the redis to reflect the new usage
        """

        # first we need to estimate the output tokens for the response
        output_tokens = self.token_budget.estimate_tokens(
            cleaned_response)

        # then we need to record the usage of the conversation/thread in redis
        """
        In some cases the record_output_usage might fail and raise an exception so we need to add exception handling here
        but incase of the failure we will not return a failure to the client since we have the response and we can return it to the client.
        so, we will just log the error and return the response to the client.
        """
        try:
            await self.chat_usage_repository.record_output_usage(
                thread_id,
                output_tokens=output_tokens,
            )

            logger.info(
                "Output token usage recorded",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "source": "agent",
                        "output_tokens": output_tokens,
                    }
                },
            )

        except Exception:
            # The response is already generated.
            # Usage recording failure is fail-open.

            logger.exception(
                "Failed to record output token usage",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                        "source": "agent",
                        "output_tokens": output_tokens,
                    }
                },
            )

        # ============================================================
        # 11. STORE RESPONSE IN CACHE
        # ============================================================

        # Only store responses produced after a cache miss.
        # We do NOT rewrite an existing cached response on a cache hit.
        # this one some times might fail and raise an exception so we need to add exception handling here
        # if the response is safe (is_output_safe is True) then we will store it in the cache otherwise we will not store it in the cache

        if is_output_safe:
            try:
                await self.cache_manager.set(
                    cleaned_message,
                    cleaned_response,
                )

                logger.info(
                    "Response stored in cache",
                    extra={
                        "extra_data": {
                            "thread_id": thread_id,
                        }
                    },
                )
            # in case of the failure we will not return a failure to the client since the response is already generated and we can return it to the client.
            # so will just log the error and return the response to the client
            except Exception as e:
                # Cache writes are fail-open.
                # The user already has a valid response.

                logger.exception(
                    "Cache store failed",
                    extra={
                        "extra_data": {
                            "thread_id": thread_id,
                        }
                    },
                )
        else:
            logger.warning(
                "Unsafe output not stored in cache",
                extra={
                    "extra_data": {
                        "thread_id": thread_id,
                    }
                },
            )

        # ============================================================
        # 12. REQUEST COMPLETED
        # ============================================================

        logger.info(
            "Chat request completed",
            extra={
                "extra_data": {
                    "thread_id": thread_id,
                    "success": True,
                    "cached": False,
                    "cache_type": None,
                    "model_used": model_used,
                    "estimated_input_tokens": (
                        estimated_input_tokens
                    ),
                    "estimated_output_tokens": output_tokens,
                }
            },
        )

        return {
            "success": True,
            "response": cleaned_response,
            "cleaned_message": cleaned_message,
            "input_security_notes": input_security_notes,
            "output_security_notes": output_security_notes,
            "cached": False,
            "cache_type": None,
            "model_used": model_used,
            "error": None,
        }
