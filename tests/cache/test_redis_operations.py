
"""
This File is supposed to test the Redis Operations functionality
use the following command to run the test:
python -m tests.cache.test_redis_operations
"""


import asyncio

from app.core.cache.redis_operations import redis_operations

# SET
#  ↓
# Redis stores the value
#  ↓
# GET
#  ↓
# Value is returned
#  ↓
# EXISTS
#  ↓
# Key exists
#  ↓
# DELETE
#  ↓
# Key is removed
#  ↓
# EXISTS
#  ↓
# Key no longer exists


async def test_redis_operations() -> None:
    test_key = "test:redis_operations"
    test_value = "Hello Redis"

    try:
        # 1. SET
        result = await redis_operations.set(
            test_key,
            test_value,
            ttl=60,
        )
        print(f"SET result: {result}")

        # 2. GET
        value = await redis_operations.get(test_key)
        print(f"GET result: {value}")

        # 3. EXISTS
        exists = await redis_operations.exists(test_key)
        print(f"EXISTS result: {exists}")

        # 4. DELETE
        deleted = await redis_operations.delete(test_key)
        print(f"DELETE result: {deleted}")

        # 5. EXISTS after DELETE
        exists_after_delete = await redis_operations.exists(test_key)
        print(f"EXISTS after DELETE: {exists_after_delete}")

    finally:
        # Safety cleanup in case something fails
        await redis_operations.delete(test_key)


if __name__ == "__main__":
    asyncio.run(test_redis_operations())
