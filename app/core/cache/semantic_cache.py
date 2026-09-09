"""
Semantic will be somehow differnet to the ExactCache, but it will still use the RedisOperations wrapper to interact with Redis. The main difference is that the key generation will be based on a semantic representation of the query, rather than an exact match. This allows for more flexible caching strategies, such as caching similar queries together.

In exact cache, we used the following approach:

User query
    ↓
Normalize
    ↓
SHA-256
    ↓
Redis key
    ↓
Exact match?


while in the Semantic cache, we will use the following approach:
User query
    ↓
Embedding model
    ↓
Vector
    ↓
Similarity search
    ↓
Similar previous query?
    ↓
Yes → return cached response
No  → continue to RAG/LLM

Original: "What is the capital of France?"

Later: "Which city is the capital of France?"

Exact Cache wont work
But their embeddings should be very similar, so the semantic cache can potentially return the previous response.

"What is Python?"
        ↓
Cached

"Can you explain what Python is?"
        ↓
Semantic similarity
        ↓
Very similar
        ↓
Return cached answer


Overall architecture:
                         User Query
                             │
                             ▼
                     ┌───────────────┐
                     │ Cache Manager │
                     └───────┬───────┘
                             │
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
             Exact Cache          Semantic Cache
                  │                     │
                  │                Generate embedding
                  │                     │
                  │                     ▼
                  │               Vector Search
                  │                     │
                  │                     ▼
                  │               Redis Vector
                  │                     │
                  └──────────┬──────────┘
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
                         Response
                             │
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
             Exact Cache          Semantic Cache


In this module we are going to care about the following two: 
1- Get: semantic_cache.get(query)
        │
        ├── generate embedding
        │
        ├── search similar queries
        │
        ├── check similarity threshold
        │
        └── return cached response / None
        
so after generating the embeddins we need to store the vectore somewhere
Note: our current redis can be extended to use Redis Vector Search instead of jus having "key -> response"
so, we can conceptually have: 
Redis
│
├── Exact cache
│      └── key → response
│
└── Semantic cache
       ├── embedding vector
       ├── original query
       └── response
       
    
and we need to choose the embedding model: what is recommended is that we use the settings configuration so later on we can change the embedding model without cache renewal


How semantic lookup works:
- Old: "What is Python?" => embedding model => [0.12, -0.34, 0.87, ...]
... 

- New: "Explain Python programming." => embedding model => [0.11, -0.33, 0.88, ...]

Then Redis will search for the vector and return the nearest cached query 

But we have a very important factor which is the similarity threshold, vector similarity should be > similarity threshold



What will Redis exactly store for the semantic cache?
{
    "query": "What is Python?",
    "response": "Python is a programming language...",
    "embedding": [0.12, -0.34, 0.87],
    "created_at": "...",
    "ttl": 300
}

the embedding is what redis uses for similarity search


Regarding the TTL Redis automatically handle the expiration but we can also use the settings variable

Pipeline Archetecture:
User Query
    │
    ▼
Exact Cache
    │
    ├── HIT → Return
    │
    └── MISS
          │
          ▼
    Semantic Cache
          │
          ├── HIT → Return
          │
          └── MISS
                │
                ▼
             RAG
                │
                ▼
              LLM
                │
                ▼
             Response
                │
         ┌──────┴──────┐
         ▼             ▼
    Exact Cache   Semantic Cache

"""

"""
The following are concerned with the implementation: 

First we need to add the following to the settings in config.py file:
- embedding_model: str = "models/gemini-embedding-001"
- embedding_dimension: int = 768
- semantic_cache_similarity_threshold: float = 0.90
- semantic_cache_top_k: int = 1

and add the following to the .env file:
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSION=768
SEMANTIC_CACHE_SIMILARITY_THRESHOLD=0.90
SEMANTIC_CACHE_TOP_K=1

After creating the embeddin model and testing it we need to create th Redis Vector index and tell it
For semantic-cache entries, the embedding field contains 768-dimensional vectors, and I want to search them using cosine similarity.

then we run the following command to create the index in Redis:
docker exec -it production-api-redis redis-cli FT.CREATE semantic_cache_idx ON HASH PREFIX 1 cache:semantic: SCHEMA query TEXT response TEXT embedding VECTOR FLAT 6 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE

Redis
│
├── Exact cache
│
└── Semantic cache
      │
      ├── semantic_cache:<id>
      │      ├── query
      │      ├── response
      │      └── embedding (768 dimensions)
      │
      └── semantic_cache_idx

The after running the command redis will have the semantic_cache_idx configured for 768-dimensional vectors, COSINE similarity
to verify run the follwing command: docker exec production-api-redis redis-cli FT.INFO semantic_cache_idx

Next we need to update the redis_client.py to create a new client the will be able to handle the set and get of the cached data for the semantic search

The problem is that the origial redis_client uses the following: decode_responses=True
and this means that whenever Redis sends the data stored back => automatically decode it from bytes into Python strings using UTF-8, for the exact cache this is what we want 
but when it comes to the semantic cache the embeddins will look like [-0.01824733, 0.00652421, ...] the it will be converted to FLOAT32 binary data => so redis will store them as C2 91 ... 0A ... FF ...
so upon retrieval decode_response = True => 
binary bytes
      ↓
decode as UTF-8
      ↓
💥 UnicodeDecodeError

to solve the problem => create new client only for semantic purpose

                    Redis
                      │
             ┌────────┴────────┐
             │                 │
          redis          redis_binary
             │                 │
      decode=True       decode=False
             │                 │
       text values      binary vectors
       
we don't simply make decode_response = False everywhere since 
async def get(...) -> Optional[str] will expect b"some cached response" instead of "some cached response"

                    Redis Container
                         │
              ┌──────────┴──────────┐
              │                     │
        Connection Pool 1     Connection Pool 2
        decode_responses=True  decode_responses=False
              │                     │
         Exact Cache          Semantic Cache
         
Final architecture:

                    Redis
                      │
          ┌───────────┴───────────┐
          │                       │
    Exact Cache              Semantic Cache
          │                       │
     text values             text + vectors
          │                       │
     redis client          redis_binary client
          │                       │
          └───────────┬───────────┘
                      │
                RedisOperations
                
Next we need to implement the set and get in the vector redis operations

        
User query
    ↓
Normalize query
    ↓
Generate Gemini embedding (768D)
    ↓
Search Redis vector index
    ↓
Calculate similarity/distance
    ↓
If sufficiently similar → CACHE HIT
    ↓
Return cached response

If no match → CACHE MISS
    ↓
LLM generates response
    ↓
Store query + response + embedding in Redis
         
"""


import numpy as np
import uuid
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import get_settings
from app.core.cache.redis_operations import redis_operations


class SemanticCache:
    """Semantic cache using Gemini embeddings and Redis vector search."""

    def __init__(self) -> None:
        self.settings = get_settings()

        self.embedder = GoogleGenerativeAIEmbeddings(
            model=self.settings.embedding_model,
            google_api_key=self.settings.gemini_api_key,
            output_dimensionality=self.settings.embedding_dimension,
        )

        self.redis = redis_operations

        self.index_name = "semantic_cache_idx"
        self.cache_prefix = "cache:semantic:"
        self.ttl = self.settings.cache_ttl_seconds

        self.similarity_threshold = (
            self.settings.semantic_cache_similarity_threshold
        )

        self.top_k = self.settings.semantic_cache_top_k

        self._hits = 0
        self._misses = 0

    def _make_key(self) -> str:
        """Create a unique Redis key for a semantic-cache entry."""
        return f"{self.cache_prefix}{uuid.uuid4().hex}"

    async def _embed(self, query: str) -> bytes:
        """Generate a FLOAT32 embedding and convert it to bytes."""
        vector = await self.embedder.aembed_query(query)

        return np.asarray(
            vector,
            dtype=np.float32,
        ).tobytes()

    async def get(self, query: str) -> str | None:
        """
        Find a semantically similar cached response.

        Returns the cached response on a hit.
        Returns None on a miss.
        """

        query_vector = await self._embed(query)

        results = await self.redis.vector_search(
            index_name=self.index_name,
            query_vector=query_vector,
            top_k=self.top_k,
        )

        if not results.docs:
            self._misses += 1
            return None

        result = results.docs[0]

        distance = float(result.distance)

        # print(f"Query: {query}")
        # print(f"Nearest cached query: {result.query}")
        # print(f"Distance: {distance}")
        # print(f"Threshold: {self.similarity_threshold}")

        if distance <= self.similarity_threshold:
            self._hits += 1
            return result.response

        self._misses += 1
        return None

    async def set(
        self,
        query: str,
        response: str,
    ) -> None:
        """Generate an embedding and store the response in Redis."""

        embedding = await self._embed(query)

        key = self._make_key()

        await self.redis.store_vector(
            key=key,
            query=query,
            response=response,
            embedding=embedding,
            ttl=self.ttl,
        )

    @property
    def stats(self) -> dict:
        """Return semantic-cache statistics."""

        total = self._hits + self._misses

        hit_rate = (
            self._hits / total
            if total > 0
            else 0.0
        )

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1%}",
        }


semantic_cache = SemanticCache()
