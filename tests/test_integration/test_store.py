from scoring_api.scoring import get_score


def test_get_score_integration(real_store):
    real_store.cache_set("uid:df772fb46c4f5942b6bf98e7c5cfdb20", 42.0, timeout=60)
    result = get_score(real_store, phone="79175002040")
    assert result == 42.0
