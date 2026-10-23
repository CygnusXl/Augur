from augur.predictors import (
    MarkovPredictor,
    NoPredictor,
    OraclePredictor,
    SequentialPredictor,
    StridePredictor,
)


def feed(p, seq):
    for x in seq:
        p.observe(x)
    return p


def items(cands):
    return [c.item for c in cands]


def test_none_predicts_nothing():
    assert feed(NoPredictor(), [1, 2, 3]).predict(4) == []


def test_sequential_needs_a_run_then_predicts_next_ids():
    p = SequentialPredictor()
    assert feed(p, [5]).predict(3) == []
    feed(p, [6])
    assert items(p.predict(3)) == [7, 8, 9]
    feed(p, [40])
    assert p.predict(3) == []  # run broken


def test_stride_detects_constant_stride():
    p = feed(StridePredictor(), [0, 7, 14, 21])
    cands = p.predict(3)
    assert items(cands) == [28, 35, 42]
    assert 0 < cands[0].confidence < 1


def test_stride_ignores_random():
    assert feed(StridePredictor(), [3, 91, 12, 55, 7]).predict(4) == []


def test_markov_learns_cycle_and_chains():
    p = MarkovPredictor(1, min_support=1, smoothing=0.0)
    feed(p, [1, 2, 3, 4] * 3 + [1])
    cands = p.predict(3)
    assert items(cands) == [2, 3, 4]
    assert all(c.confidence == 1.0 for c in cands)


def test_markov_unseen_context_returns_empty():
    p = feed(MarkovPredictor(2), [1, 2, 3])
    feed(p, [99])
    assert p.predict(4) == []


def test_markov_smoothing_tempers_single_observation():
    naive = feed(MarkovPredictor(1, min_support=1, smoothing=0.0), [1, 2, 1])
    careful = feed(MarkovPredictor(1, min_support=2), [1, 2, 1])
    assert naive.predict(1)[0].confidence == 1.0
    assert careful.predict(1) == []  # one observation is below min_support


def test_markov_confidence_reflects_ambiguity():
    p = MarkovPredictor(1, min_support=1, smoothing=0.0)
    feed(p, [1, 2, 1, 2, 1, 3, 1])
    c = p.predict(1)[0]
    assert c.item == 2 and abs(c.confidence - 2 / 3) < 1e-9


def test_markov_backoff_to_lower_order():
    p = MarkovPredictor(2, min_support=1, smoothing=0.0)
    feed(p, [1, 2, 3, 9, 2, 3])  # context (9,2) -> 3 seen; context (2,3) never has a successor
    assert items(p.predict(1)) == [9]  # falls back to order 1: 3 -> 9


def test_oracle_is_exact():
    acc = [4, 8, 15, 16, 23, 42]
    p = OraclePredictor(acc)
    feed(p, acc[:2])
    assert items(p.predict(3)) == [15, 16, 23]
    feed(p, acc[2:])
    assert p.predict(3) == []


def test_invalid_order():
    import pytest
    with pytest.raises(ValueError):
        MarkovPredictor(0)
