import redis
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class PromptCache:
    def __init__(self):
        # Use existing Redis connection from Celery
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        self.default_ttl = 24 * 60 * 60  # 24 hours
    
    def get(self, key: str):
        """Get a value from cache"""
        try:
            cache_key = f"prompt_cache:{key}"
            value = self.redis_client.get(cache_key)
            if value:
                decoded_value = value.decode('utf-8')
                logger.debug(f"Cache HIT for {key}: {decoded_value[:50]}...")
                return decoded_value
            else:
                logger.debug(f"Cache MISS for {key}")
                return None
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None
    
    def set(self, key: str, value: str, ttl: int = None):
        """Set a value in cache with TTL"""
        try:
            ttl = ttl or self.default_ttl
            cache_key = f"prompt_cache:{key}"
            self.redis_client.setex(cache_key, ttl, value)
            logger.debug(f"Cache SET for {key}: {value[:50]}...")
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
    
    def delete(self, key: str):
        """Delete a value from cache"""
        try:
            self.redis_client.delete(f"prompt_cache:{key}")
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
    
    def clear_all(self):
        """Clear all prompt cache entries - useful for testing"""
        try:
            # Get all keys matching our pattern and delete them
            pattern = "prompt_cache:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cache keys: {keys}")
            else:
                logger.info("No cache keys to clear")
        except Exception as e:
            logger.warning(f"Cache clear_all failed: {e}")

# Global cache instance
prompt_cache = PromptCache() 