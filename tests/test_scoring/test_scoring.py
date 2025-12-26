

import pytest
from datetime import datetime
import json
import redis
from scoring_api.scoring import get_score, get_interests
from scoring_api.store import Storage


def test_get_score_calculation_cache_set(mocker):
    store = mocker.MagicMock()
    store.cache_get.return_value = None

    score = get_score(
        store,
        phone="79175002040",
        email="test_scoring@example.com",
        birthday=datetime(2000, 1, 1),
        gender=1,
        first_name="John",
        last_name="Doe"
    )
    assert score == 5.0
    store.cache_set.assert_called_once()
    args, kwargs = store.cache_set.call_args
    assert args[1] == 5.0
    assert args[2] == 3600


def test_get_score_returns_cached_value(mocker):
    store = mocker.MagicMock()
    store.cache_get.return_value = "5.5"

    score = get_score(store, phone="79175002040")
    assert score == 5.5
    store.cache_set.assert_not_called()


def test_get_score_with_store_unavailable(mocker):
    redis_store_mock = mocker.MagicMock()
    redis_store_mock.get.side_effect = redis.exceptions.ConnectionError
    store = Storage(redis_store_mock)

    result = get_score(store, phone="79175002040")
    assert result == 1.5


@pytest.mark.parametrize("cid, json_str, expected", [
    ("123", '["cinema", "geek"]', ["cinema", "geek"]),
    ("999", None, []),
])
def test_get_interests(cid, json_str, expected, mocker):
    store = mocker.MagicMock()
    store.get.return_value = json_str

    result = get_interests(store, cid)
    assert result == expected


def test_get_interests_invalid_json(mocker):
    store = mocker.MagicMock()
    store.get.return_value = "invalid_json"

    with pytest.raises(json.JSONDecodeError):
        get_interests(store, "123")


def test_get_interests_connection_error(mocker):
    redis_store_mock = mocker.MagicMock()
    redis_store_mock.get.side_effect = redis.exceptions.ConnectionError

    store = Storage(redis_store_mock)

    with pytest.raises(redis.exceptions.ConnectionError):
        get_interests(store, "123")
