"""
Redis repository for chat token usage.

Responsible for:
- Loading usage for a chat
- Recording token usage for a chat
- Persisting usage in Redis
- Sharing usage across FastAPI workers

So instead of ChatUsage being stored only in Python memory, this repository stores the values in Redis.
and this is important since we have multiple FastAPI workers and they all can read and update the same usage inforamtion 
=> without redis each worker would have its own ChatUsage object in memory and they would not be able to share the usage information

important note: Worker here means a separate FastAPI process running the FastAPI application.
so when we run something like uvicorn app.main:app --workers 3
client request => FastAPI worker 1 => ChatUsage object in memory
client request => FastAPI worker 2 => ChatUsage object in memory
client request => FastAPI worker 3 => ChatUsage object in memory
so each worker has its own ChatUsage object in memory and they would not be able to share the usage information
but if we use Redis, all workers can read and update the same usage information in Redis

why is this a problem? assume that one client with a chat_id chat-123 is sending request 1 to worker 1 and request 2 happens to be sent to worker 2
if the ChatUsage is in memory, worker 1 will have its own ChatUsage object in memory and worker 2 will have its own ChatUsage object in memory
so when request 1 is processed by worker 1, it will update its own ChatUsage
and when request 2 is processed by worker 2, it will update its own ChatUsage
so the total usage will not be accurate since worker 1 and worker 2 are not sharing

                Redis
                  │
        chat-123 usage
        requests = 10
        tokens = 8500
                  │
          ┌───────┼───────┐
          ↓       ↓       ↓
       Worker 1 Worker 2 Worker 3
       
       
And just not to make conflicts with redis_client => when we create a new process (worker) of the FastAPI application, the lifespan will create a new Redis client for that worker => each worker will have its own connection pool to the Redis server
=> but all these workers will be sharing the same Redis server and the same Redis data (chat usage information)

Worker 1
  └── Redis client/pool ──┐

Worker 2
  └── Redis client/pool ──┼──> Same Redis container/server

Worker 3
  └── Redis client/pool ──┘
  
and thats why we also used the Redis pipeline to make sure that the increment operations are atomic and we don't have race conditions when multiple workers are trying to update the same chat usage information in Redis at the same time

Now the confusion comes when we say that two different workers might happen to race who is going to update the chat usage first. which means that the client is send request concurrently and not one request at a time
This is possible since the client might be sending multiple requests at a time to different processes (workers) of the FastAPI application and they might happen to be processing the same chat_id at the same time

for example if the user is having two browser tabs, mobile and web, retries after a network timeout => all using the same chat_id and sending the requests at the same time to different workers of the FastAPI application

"""
# this imports the Redis client that we already created in the redis_client
from app.core.redis.redis_client import redis_client

# this imports the ChatUsage data model which will include info about the total input tokens, total output tokens, and total requests for a chat
from app.core.token_budget.chat_usage import ChatUsage


"""
This is the Lua script that will be sent to Reids to be executed atomically.

It will check if the request is allowed based on the current usage, and if allowed, it will increment the usage in Redis.

1- Recieve the estimated input tokens, max chat tokens, and max requests per chat as arguments
2- Read the current usage from Redis (total input tokens, total output tokens, total requests)
3- Check if the request is within the allowed limits
4- If allowed, increment the usage in Redis
"""

RESERVE_REQUEST_SCRIPT = """
local key = KEYS[1]

local estimated_input_tokens = tonumber(ARGV[1])
local max_chat_tokens = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])

local total_input = tonumber(redis.call(
    'HGET',
    key,
    'total_input_tokens'
) or '0')

local total_output = tonumber(redis.call(
    'HGET',
    key,
    'total_output_tokens'
) or '0')

local total_requests = tonumber(redis.call(
    'HGET',
    key,
    'total_requests'
) or '0')

if total_requests >= max_requests then
    return {0, 'request_limit'}
end

local current_total_tokens =
    total_input + total_output

local projected_tokens =
    current_total_tokens + estimated_input_tokens

if projected_tokens > max_chat_tokens then
    return {0, 'token_limit'}
end

redis.call(
    'HINCRBY',
    key,
    'total_input_tokens',
    estimated_input_tokens
)

redis.call(
    'HINCRBY',
    key,
    'total_requests',
    1
)

return {1, 'allowed'}
"""

"""
Note that redis will store raw values for example {"total_input_tokens": 100, "total_output_tokens": 200, "total_requests": 5} but when it comes to the Python application it should deal with proper Python object 

So, this repository is responsible for converting the raw values from Redis into a proper Python object (ChatUsage) and vice versa when saving the usage back to Redis.
"""


# This defines the repository class
# A repository is basically a layer responsible for reading and writing data to a data source (in this case Redis) and converting it into proper Python objects (in this case ChatUsage)

"""
In general this class is responsible for storing adn retrieving the chat token usage

TokenBudget is responsible for defining and enforcing the rules/policiec

ChatUsage is responsible for keeping track of the state of a single chat/session

TokenBudget (rules) => ChatUsage (state) => ChatUsageRepository (persistence) => Redis (data)


"""


class ChatUsageRepository:
    """Redis-backed repository for chat token usage."""

    # This creates a class constant.
    KEY_PREFIX = "token_usage:chat"

    """
    for example if we have a chat-123 is the chat ID then the actual redis Key becomes: token_usage:chat:chat-123
    
    => this creates a clear namespace in Redis
    so redis server will contain: 
    - exact_cache:...
    - semantic_cache:...
    - token_usage:chat:chat-123
    - token_usage:chat:chat-456
    """

    def __init__(self) -> None:
        self.redis = redis_client.redis

    def _make_key(self, chat_id: str) -> str:
        """Create the Redis key for one chat."""
        return f"{self.KEY_PREFIX}:{chat_id}"

    """
    It is async because Redis access is network I/O.
    Even though Redis is running locally in Docker, Python still communicates with it through a network connection.
    Therefore we don't want to block FastAPI while waiting for Redis.
    
    This method loads usage for one chat.
    """

    async def get_usage(
        self,
        chat_id: str,
    ) -> ChatUsage:
        """
        Return usage for one chat.

        If the chat has no existing usage,
        return a new empty ChatUsage object.
        """

        key = self._make_key(chat_id)

        # Get every field/value pair from a Redis Hash.
        data = await self.redis.hgetall(key)

        if not data:
            return ChatUsage()
            # this will be a new ChatUsage object with all values set to 0
            # total_input_tokens = 0
            # total_output_tokens = 0
            # total_requests = 0

        # If Redis does have existing data, we reach:
        # Redis returns {"total_input_tokens": "500"} it is stored and returned as a string value => we change it to int
        return ChatUsage(
            total_input_tokens=int(
                data.get("total_input_tokens", 0)
            ),
            total_output_tokens=int(
                data.get("total_output_tokens", 0)
            ),
            total_requests=int(
                data.get("total_requests", 0)
            ),
        )

    #
    """
    Now this code below is vert important part since as we mentioned at the beginning is that sometimes we could have multiple workers of the FastAPI application recieving requests from the same client with the same chat_id
    This is solving the problem of race conditions when multiple workers are trying to update the same chat usage
    
    but some time it is not even safe to make further updates or allow the user to proceed with the request.
    for example we have the following scenario:
    - for the same chat_id, worker 1 reads 49 and check < 50 => allowed
    - for the same chat_id, worker 2 reads 49 and check < 50 => allowed
    
    - worker 1 proceed to increment the usage by 1 => 50
    - worker 2 proceed to increment the usage by 1 => 51
    => the update was correct but the limit was violated
    
    That entire sequence must be atomic forstrict production enforcement.
    to solve the above problem is simlpy by doing the below method which is automatically read the current usage checks request/token limits if allowed theen record the usage in one atomic operation
    so it is going to send allowed or denied
    """

    """
    This method below does three main things: 
    1. Read the current usage for the chat.
    2. Check if the request is within the allowed limits.
    3. If allowed, record the usage in one atomic operation.
    
    """

    async def reserve_request(
        self,
        chat_id: str,
        estimated_input_tokens: int,
        max_chat_tokens: int,
        max_requests_per_chat: int,
    ) -> tuple[bool, str | None]:

        key = self._make_key(chat_id)
        """
        This reserve_request method will call the eval() method which will send the Lua script to Redis
        then redis will execute the Lua script atomically and return the result to the Python application.
        """

        result = await self.redis.eval(
            RESERVE_REQUEST_SCRIPT,
            1,
            key,
            estimated_input_tokens,
            max_chat_tokens,
            max_requests_per_chat,
        )

        allowed = bool(result[0])
        reason = result[1]

        """
        if allowed is True it means that the update usage is reserved for the current call (the current worker) and the user can proceed with the request
        => it will also increment the total_input_tokens and total_requests in Redis for the current chat_id
        
        if not allowed it means that the user has exceeded the limits and the request should be denied and the reason will be either "request_limit" or "token_limit"
        """
        
        if allowed:
            return True, None

        if reason == "request_limit":
            return False, "Maximum requests per chat exceeded."

        if reason == "token_limit":
            return False, "Maximum token budget for chat exceeded."

        return False, "Token budget check failed."

    async def record_output_usage(
        self,
        chat_id: str,
        output_tokens: int,
    ) -> None:
        """
        Record output-token usage after the LLM finishes.

        Input tokens and request count were already reserved
        by reserve_request(), so they must not be incremented
        again here.
        """

        key = self._make_key(chat_id)

        await self.redis.hincrby(
            key,
            "total_output_tokens",
            output_tokens,
        )


# This creates one reusable repository instance at module level.
# so other parts can do from app.core.token_budget.usage_repository import (chat_usage_repository,) rather than repeatedly creating new instances of ChatUsageRepository.
chat_usage_repository = ChatUsageRepository()

"""
The above line of code is simply at the level of the FastAPI application process and it does not mean that it is shared across multiple FastAPI workers. 
In case we don't write the above line of code then each module or service need this repository will create its own instance of the ChatUsageRepository class
so: 

ChatService
    ↓
ChatUsageRepository()  ← object 1

Another service
    ↓
ChatUsageRepository()  ← object 2

Another component
    ↓
ChatUsageRepository()  ← object 3

You're unnecessarily constructing repository objects repeatedly.

while with the above line of code,
Python will create one instance of the ChatUsageRepository class and from another filw we can simply imporrt it using 
from app.core.token_budget.usage_repository import (
    chat_usage_repository,
)

"""

"""
Additional note about the some case

we might face the following scenario:
The request is allowed and the usage is reserved for the current call (the current worker) and the user can proceed with the request => input tokens and request count are updated
but after the LLM fails to respond or the request is cancelled by the user => the output tokens are not recorded and the usage is not updated => the usage is not accurate

for production this is fine since the user has already consumed the input tokens and the request count -or the resources- are already accounted for.
reserve_request()
→ increment input tokens
→ increment request count

call LLM
→ success
   → record output tokens

→ failure
   → do not record output tokens
   → keep input tokens + request count

but based on preference we can implement a rollback mechanism to decrement the input tokens and request count in case of failure or canellation of the request
"""



# The repository itself doesn't store per-chat usage in Python memory.
# It only points to the shared Redis client
# Therefore one repository instance is sufficient for the entire FastAPI application.
# One particularly important point: ChatUsage itself is not being persisted as a Python object. Redis stores only the individual hash fields. ChatUsageRepository reconstructs a ChatUsage object whenever the application needs one
