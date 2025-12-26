import pytest
import redis
from scoring_api.store import RedisStore, Storage


@pytest.fixture
def redis_store():
    return RedisStore()


@pytest.fixture
def storage(redis_store):
    return Storage(redis_store)


@pytest.fixture
def context():
    return {}


@pytest.fixture
def headers():
    return {}


@pytest.fixture
def real_store():
    r = redis.Redis(host="localhost", port=6379, db=1)
    r.flushdb()
    store = Storage(r)
    yield store
    r.flushdb()
