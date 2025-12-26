import pytest
from unittest.mock import MagicMock
import redis
from scoring_api.scoring import get_interests
from scoring_api.store import Storage


def test_retry_behavior():
    redis_store_mock = MagicMock()
    redis_store_mock.get.side_effect = [redis.exceptions.ConnectionError,
                                        redis.exceptions.ConnectionError,
                                        b'[1,2,3]']

    store = Storage(redis_store_mock)

    result = get_interests(store, "123")
    assert result == [1, 2, 3]

    assert redis_store_mock.get.call_count == 3


def test_retry_behavior_failed():
    redis_store_mock = MagicMock()
    redis_store_mock.get.side_effect = redis.exceptions.ConnectionError
    store = Storage(redis_store_mock)

    with pytest.raises(redis.exceptions.ConnectionError):
        store.get("123")

    assert redis_store_mock.get.call_count == 4
