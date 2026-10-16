"""
Market Basket Analysis (Apriori-style frequent itemsets + association rules).

Requires true transaction/basket sets — never construct baskets from same-day
Favorita daily aggregates.
"""

from __future__ import annotations

import itertools
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.basket_transaction import BasketTransaction
from app.models.product_association import ProductAssociation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssociationRule:
    antecedent_sku: str
    consequent_sku: str
    support: float
    confidence: float
    lift: float

    def as_dict(self) -> dict:
        return asdict(self)


def build_baskets_from_rows(
    rows: Iterable[tuple[str, str]],
) -> list[frozenset[str]]:
    """
    Group (transaction_id, sku) lines into baskets (sets of SKUs).

    Quantity is ignored for presence-based MBA (item in basket or not).
    """
    buckets: dict[str, set[str]] = defaultdict(set)
    for txn_id, sku in rows:
        tid = str(txn_id).strip()
        s = str(sku).strip()
        if not tid or not s:
            continue
        buckets[tid].add(s)
    return [frozenset(items) for items in buckets.values() if len(items) >= 1]


def _item_supports(baskets: list[frozenset[str]], min_support: float) -> dict[frozenset[str], float]:
    n = len(baskets)
    if n == 0:
        return {}
    counts: dict[frozenset[str], int] = defaultdict(int)
    for basket in baskets:
        for item in basket:
            counts[frozenset([item])] += 1
    return {itemset: c / n for itemset, c in counts.items() if (c / n) >= min_support}


def _generate_candidates(prev_freq: list[frozenset[str]], k: int) -> list[frozenset[str]]:
    out: list[frozenset[str]] = []
    for a, b in itertools.combinations(sorted(prev_freq, key=lambda x: tuple(sorted(x))), 2):
        union = a | b
        if len(union) == k:
            out.append(union)
    # Deduplicate
    return list({c for c in out})


def mine_frequent_itemsets(
    baskets: list[frozenset[str]],
    *,
    min_support: float = 0.01,
    max_itemset_size: int = 2,
) -> dict[frozenset[str], float]:
    """Apriori frequent itemsets up to ``max_itemset_size`` (default pairs only)."""
    if not baskets:
        return {}
    if min_support <= 0 or min_support > 1:
        raise ValueError("min_support must be in (0, 1]")
    if max_itemset_size < 1:
        raise ValueError("max_itemset_size must be >= 1")

    n = len(baskets)
    freq = _item_supports(baskets, min_support)
    all_freq = dict(freq)
    prev = list(freq.keys())
    k = 2
    while prev and k <= max_itemset_size:
        candidates = _generate_candidates(prev, k)
        counts: dict[frozenset[str], int] = defaultdict(int)
        cand_set = set(candidates)
        for basket in baskets:
            for cand in cand_set:
                if cand.issubset(basket):
                    counts[cand] += 1
        next_freq = {
            itemset: c / n for itemset, c in counts.items() if (c / n) >= min_support
        }
        all_freq.update(next_freq)
        prev = list(next_freq.keys())
        k += 1
    return all_freq


def association_rules_from_itemsets(
    freq: dict[frozenset[str], float],
    *,
    min_confidence: float = 0.1,
    min_lift: float = 1.0,
) -> list[AssociationRule]:
    """
    Build directed A⇒B rules from frequent itemsets (primarily size-2 pairs).

    Does not auto-add B⇒A unless that reverse rule independently passes thresholds.
    """
    if min_confidence <= 0 or min_confidence > 1:
        raise ValueError("min_confidence must be in (0, 1]")
    singles = {next(iter(s)): supp for s, supp in freq.items() if len(s) == 1}
    rules: list[AssociationRule] = []
    for itemset, supp_ab in freq.items():
        if len(itemset) != 2:
            continue
        a, b = tuple(sorted(itemset))
        for ante, cons in ((a, b), (b, a)):
            supp_a = singles.get(ante)
            supp_b = singles.get(cons)
            if not supp_a or not supp_b or supp_a <= 0:
                continue
            confidence = supp_ab / supp_a
            lift = confidence / supp_b if supp_b > 0 else 0.0
            if confidence < min_confidence or lift < min_lift:
                continue
            rules.append(
                AssociationRule(
                    antecedent_sku=ante,
                    consequent_sku=cons,
                    support=float(supp_ab),
                    confidence=float(confidence),
                    lift=float(lift),
                )
            )
    rules.sort(key=lambda r: (r.lift, r.confidence, r.support), reverse=True)
    return rules


def load_baskets_from_db(
    db: Session,
    *,
    store_id: str | None = None,
    max_baskets: int | None = None,
) -> list[frozenset[str]]:
    stmt = select(BasketTransaction.transaction_id, BasketTransaction.sku)
    if store_id is not None:
        stmt = stmt.where(BasketTransaction.store_id == store_id)
    else:
        # Online Retail II / global: prefer rows with no fabricated store.
        stmt = stmt.where(BasketTransaction.store_id.is_(None))
    rows = db.execute(stmt).all()
    baskets = build_baskets_from_rows((r.transaction_id, r.sku) for r in rows)
    # Keep multi-item baskets only for association mining.
    baskets = [b for b in baskets if len(b) >= 2]
    if max_baskets is not None and max_baskets > 0 and len(baskets) > max_baskets:
        # Deterministic subsample: largest baskets first (more co-occurrence signal).
        baskets = sorted(baskets, key=len, reverse=True)[:max_baskets]
    return baskets


def generate_and_persist_associations(
    db: Session,
    *,
    store_id: str | None = None,
    min_support: float = 0.01,
    min_confidence: float = 0.2,
    min_lift: float = 1.0,
    max_itemset_size: int = 2,
    max_baskets: int | None = None,
    replace: bool = True,
) -> list[AssociationRule]:
    """
    Mine rules from ``basket_transactions`` and persist into ``product_associations``.

    Returns [] (and logs) when no basket data exists — never fabricates baskets
    from daily aggregates.
    """
    baskets = load_baskets_from_db(db, store_id=store_id, max_baskets=max_baskets)
    if not baskets:
        logger.info(
            "MBA generate: no basket_transactions for store_id=%s — "
            "daily aggregated sales cannot be used as baskets",
            store_id,
        )
        return []

    freq = mine_frequent_itemsets(
        baskets, min_support=min_support, max_itemset_size=max_itemset_size
    )
    rules = association_rules_from_itemsets(
        freq, min_confidence=min_confidence, min_lift=min_lift
    )

    if replace:
        del_stmt = delete(ProductAssociation)
        if store_id is None:
            del_stmt = del_stmt.where(ProductAssociation.store_id.is_(None))
        else:
            del_stmt = del_stmt.where(ProductAssociation.store_id == store_id)
        db.execute(del_stmt)

    now = datetime.now(timezone.utc)
    for rule in rules:
        db.add(
            ProductAssociation(
                antecedent_sku=rule.antecedent_sku,
                consequent_sku=rule.consequent_sku,
                store_id=store_id,
                support=rule.support,
                confidence=rule.confidence,
                lift=rule.lift,
                generated_at=now,
            )
        )
    db.flush()
    logger.info(
        "MBA generate: baskets=%s rules=%s store_id=%s min_support=%s min_confidence=%s min_lift=%s",
        len(baskets),
        len(rules),
        store_id,
        min_support,
        min_confidence,
        min_lift,
    )
    return rules
