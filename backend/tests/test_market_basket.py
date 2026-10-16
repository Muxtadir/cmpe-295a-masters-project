"""Unit tests for Market Basket Analysis (no Favorita daily fabrication)."""

from __future__ import annotations

import pytest

from app.services.market_basket import (
    association_rules_from_itemsets,
    build_baskets_from_rows,
    mine_frequent_itemsets,
)


def test_build_baskets_groups_by_transaction_id():
    rows = [
        ("t1", "A"),
        ("t1", "B"),
        ("t2", "A"),
        ("t2", "C"),
        ("t3", "A"),
        ("t3", "B"),
        ("t3", "C"),
    ]
    baskets = build_baskets_from_rows(rows)
    assert len(baskets) == 3
    assert frozenset({"A", "B"}) in baskets


def test_support_confidence_lift_and_thresholds():
    # 4 baskets: AB, AB, AC, B
    baskets = [
        frozenset({"A", "B"}),
        frozenset({"A", "B"}),
        frozenset({"A", "C"}),
        frozenset({"B"}),
    ]
    freq = mine_frequent_itemsets(baskets, min_support=0.25, max_itemset_size=2)
    # A appears in 3/4 = 0.75; AB in 2/4 = 0.5
    assert freq[frozenset({"A"})] == pytest.approx(0.75)
    assert freq[frozenset({"A", "B"})] == pytest.approx(0.5)

    # conf(A→B) = 0.5/0.75; P(B)=0.75; lift≈0.889 < 1 → filtered when min_lift=1
    high = association_rules_from_itemsets(freq, min_confidence=0.5, min_lift=1.0)
    assert not any(r.antecedent_sku == "A" and r.consequent_sku == "B" for r in high)
    rules = association_rules_from_itemsets(freq, min_confidence=0.5, min_lift=0.5)
    ab = next(r for r in rules if r.antecedent_sku == "A" and r.consequent_sku == "B")
    assert ab.support == pytest.approx(0.5)
    assert ab.confidence == pytest.approx(0.5 / 0.75)
    assert ab.lift == pytest.approx((0.5 / 0.75) / 0.75)


def test_min_support_filters_rare_pairs():
    baskets = [frozenset({"A", "B"}), frozenset({"C"}), frozenset({"D"}), frozenset({"E"})]
    freq = mine_frequent_itemsets(baskets, min_support=0.4, max_itemset_size=2)
    assert frozenset({"A", "B"}) not in freq


def test_no_auto_symmetric_duplicate_unless_mined():
    baskets = [
        frozenset({"A", "B"}),
        frozenset({"A", "B"}),
        frozenset({"A"}),
        frozenset({"A"}),
    ]
    freq = mine_frequent_itemsets(baskets, min_support=0.25, max_itemset_size=2)
    rules = association_rules_from_itemsets(freq, min_confidence=0.9, min_lift=0.5)
    # A→B: supp_ab=0.5, supp_a=1.0, conf=0.5 — filtered by min_confidence 0.9
    assert all(not (r.antecedent_sku == "A" and r.consequent_sku == "B" and r.confidence >= 0.9) for r in rules)


def test_empty_baskets_yield_no_rules():
    assert mine_frequent_itemsets([], min_support=0.1) == {}
    assert association_rules_from_itemsets({}, min_confidence=0.1, min_lift=1.0) == []
