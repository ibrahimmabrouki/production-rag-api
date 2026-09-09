"""
Centralized Configuration for the application.
Use pydantic-settings for validated environement variables
"""

# this will allow us to extend the BaseSettings class to create our own settings class
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# this will allow us to cache the settings object so that we don't have to create a new one every time we need it
from functools import lru_cache

# what is pydantic-settings:
# instead of manually doing: os.getenv("GEMINI_API_KEY")
# pydantic-settings automatically reads the environment variables and validate them
# for example, if we have a variable that is supposed to be an integer, pydantic-settings will automatically convert it to an integer and raise an error if it can't be converted


# now the settings class:
# what we are creating here is application configuration object
# everything that is related to the configuration will live here
# Settings
#  ├── Gemini
#  ├── LangSmith
#  ├── application
#  ├── rate limiting
#  ├── caching
#  └── retry configuration

# This is cleaner than scattering configuration throughout your project.

# there is no default value for the gemini_api_key, langchain_api_key, and langchain_project because they are required and must be provided in the .env file or as environment variables

# but for example, this one has defaulyt value for the primary_model and fallback_model because they are optional and can be overridden in the .env file or as environment variables
# primary_model: str = "gemini-3.6-flash"

# why this is better than just using os.getenv(...):
# since incase there is no variable in the .env the pydantic-settings will raise an error and we will know that we need to provide it
# instead of just returning None and we will have to debug it later on when the application fails to start because of missing configuration

# pydantic will also validate the type of the variable
# for example, if we have: CACHE_TTL_SECONDS=300 in .env file, it will be converted to an integer automatically
# => settings.cache_ttl_seconds will be an integer and not a string

# model_config: this tells which Pydentic settings to use, in this case we are using the .env file and ignoring any extra variables that are not defined in the Settings class
# for example, if we have a variable that is not defiend in the settings and already there in the .env file, => it will be ignored and not raise an error

# @property: this will create a computed property that will return True if the app_env is production and False otherwise
# so we can use it like this: if settings.is_production: ...

# @lru_cache:
# without caching: we need to call this method every time
# def get_settings():
# return Settings()

# with caching: we only need to call this method once and it will be cached for future calls
# First call
#     ↓
# Create Settings
#     ↓
# Cache it

# Second call
#     ↓
# Return cached Settings

# Third call
#     ↓
# Return cached Settings

# this is how it will be used in the application:
# from app.core.config import get_settings

# settings = get_settings()


class Settings(BaseSettings):
    """Application configuration."""

    # LLM configuration
    gemini_api_key: str
    primary_model: str = "gemini-3.6-flash"
    fallback_model: str = "gemini-1.5-turbo"

    # LangSmith configuration
    langchain_tracing_v2: bool = True
    langchain_api_key: str
    langchain_project: str

    # Application configuration
    app_env: str = "development"
    log_level: str = "INFO"
    rate_limit: str = "20/minute"
    cache_ttl_seconds: int = 300
    max_retries: int = 3
    
    # Budget configuration
    token_max_input: int = Field(default=4000, gt=0)
    token_max_chat: int = Field(default=20000, gt=0)
    token_max_requests_per_chat: int = Field(default=50, gt=0)

    # Redis configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 20
    redis_socket_timeout: float = 5.0
    redis_socket_connect_timeout: float = 5.0
    redis_health_check_interval: int = 30

    # Embedding configuration
    embedding_model: str = "models/gemini-embedding-001"
    embedding_dimension: int = 768
    semantic_cache_similarity_threshold: float = 0.20
    semantic_cache_top_k: int = 1
    
    # Grafana configuration
    monitoring_enabled: bool = True
    grafana_otlp_endpoint: str = ""
    grafana_instance_id: str = ""
    grafana_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


# this is a fuction that will cache the settings object once then it will be reused everywhere
# so no reading of the .env file on every request
@lru_cache
def get_settings() -> Settings:
    """Cached settings instance - loaded once, resued everywhere"""
    return Settings()
