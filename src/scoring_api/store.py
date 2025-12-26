import redis

from scoring_api.utils import retry


class RedisStore:
    def __init__(self, host="localhost", port=6379, db=0):
        self.client = redis.StrictRedis(host=host, port=port, db=db)

    def set(self, key, value, timeout):
        self.client.set(key, value, timeout)

    def get(self, key):
        return self.client.get(key)

    def delete(self, key):
        self.client.delete(key)


class Storage:
    def __init__(self, redis_store: RedisStore):
        self.redis_store = redis_store

    @retry(times=3, exceptions=(redis.exceptions.ConnectionError,))
    def cache_get(self, key):
        try:
            value = self.redis_store.get(key)
            return value
        except Exception:
            pass

    @retry(times=3, exceptions=(redis.exceptions.ConnectionError,))
    def cache_set(self, key, value, timeout):
        try:
            self.redis_store.set(key, value, timeout)
        except Exception:
            pass

    @retry(times=3, exceptions=(redis.exceptions.ConnectionError,))
    def get(self, key):
        return self.redis_store.get(key)

    @retry(times=3, exceptions=(redis.exceptions.ConnectionError,))
    def set(self, key, value, timeout):
        self.redis_store.set(key, value, timeout)
