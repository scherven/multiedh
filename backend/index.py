"""
In-memory deck index built from a list of decks (each deck = set of card names).

Result categories returned by query():
  - results          : cards sorted by inclusion in matching decks
  - unique_includes  : cards overrepresented vs. overall population (high lift)
  - packages         : clusters of cards that tend to appear together
  - anti_correlations: cards underrepresented vs. overall population (low lift)
  - exclusive        : cards more common in the full combo than in any single input's decks
  - consensus        : scalar [0,1] — how similar matching decks are to each other
"""

from __future__ import annotations
import random
from collections import defaultdict
from intersection import (
    ResultEntry,
    UniqueEntry,
    PackageEntry,
    AntiCorrelationEntry,
    ExclusiveEntry,
)

# ── Tuning knobs ─────────────────────────────────────────────────────────────
MIN_INCLUSION = 0.05
MIN_UNIQUE_LIFT = 2.0
MIN_UNIQUE_INCLUSION = 0.10
MAX_ANTI_LIFT = 0.5
MIN_ANTI_OVERALL = 0.05
MIN_ANTI_MATCHING = 0.01
PACKAGE_LIFT_THRESHOLD = 2.5
PACKAGE_TOP_N = 60
MIN_PACKAGE_SIZE = 2
MAX_PACKAGE_SIZE = 6
EXCLUSIVITY_TOP_N = 50
CONSENSUS_SAMPLE_PAIRS = 200
# ─────────────────────────────────────────────────────────────────────────────


class DeckIndex:
    def __init__(self) -> None:
        self.decks: list[set[str]] = []
        self.inverted: dict[str, set[int]] = defaultdict(set)
        self._overall: dict[str, float] = {}

    def build(self, decks: list[set[str]]) -> None:
        self.decks = decks
        self.inverted = defaultdict(set)
        counts: dict[str, int] = defaultdict(int)
        for i, deck in enumerate(decks):
            for card in deck:
                self.inverted[card].add(i)
                counts[card] += 1
        total = len(decks)
        self._overall = {c: n / total for c, n in counts.items()} if total else {}

    @property
    def loaded(self) -> bool:
        return len(self.decks) > 0

    def query(
        self,
        input_cards: list[str],
    ) -> tuple[
        list[ResultEntry],
        list[UniqueEntry],
        list[PackageEntry],
        list[AntiCorrelationEntry],
        list[ExclusiveEntry],
        float,
    ]:
        if not input_cards or not self.loaded:
            return [], [], [], [], [], 0.0

        # 1. Matching decks — must contain ALL input cards
        normalized = [c.lower() for c in input_cards]
        sets = [self.inverted.get(c, set()) for c in normalized]
        matching: set[int] = sets[0].copy()
        for s in sets[1:]:
            matching &= s

        if not matching:
            return [], [], [], [], [], 0.0

        n_matching = len(matching)
        excluded = set(normalized)

        # 2. Count every other card across matching decks
        counts: dict[str, int] = defaultdict(int)
        for idx in matching:
            for card in self.decks[idx]:
                if card not in excluded:
                    counts[card] += 1

        # 3. Result entries
        entries: list[ResultEntry] = []
        for card, cnt in counts.items():
            inc = cnt / n_matching
            if inc >= MIN_INCLUSION:
                entries.append(ResultEntry(name=card, inclusion=inc, num_decks=cnt))
        entries.sort(key=lambda e: e["inclusion"], reverse=True)
        results = entries

        unique = self._compute_unique(entries)
        packages = _find_packages(entries[:PACKAGE_TOP_N], matching, self.decks, n_matching)
        anti = self._compute_anti(entries)
        exclusive = self._compute_exclusive(entries[:EXCLUSIVITY_TOP_N], normalized, n_matching) if len(normalized) >= 2 else []
        consensus = _compute_consensus(matching, self.decks)

        return results, unique, packages, anti, exclusive, consensus

    def _compute_unique(self, entries: list[ResultEntry]) -> list[UniqueEntry]:
        unique: list[UniqueEntry] = []
        for e in entries:
            overall = self._overall.get(e["name"], 0)
            if overall == 0:
                continue
            lift = e["inclusion"] / overall
            if lift >= MIN_UNIQUE_LIFT and e["inclusion"] >= MIN_UNIQUE_INCLUSION:
                unique.append(UniqueEntry(name=e["name"], inclusion=e["inclusion"], overall_inclusion=overall, lift=lift))
        unique.sort(key=lambda u: u["lift"], reverse=True)
        return unique

    def _compute_anti(self, entries: list[ResultEntry]) -> list[AntiCorrelationEntry]:
        anti: list[AntiCorrelationEntry] = []
        for e in entries:
            overall = self._overall.get(e["name"], 0)
            if overall < MIN_ANTI_OVERALL or e["inclusion"] < MIN_ANTI_MATCHING:
                continue
            anti_lift = e["inclusion"] / overall
            if anti_lift <= MAX_ANTI_LIFT:
                anti.append(AntiCorrelationEntry(name=e["name"], inclusion=e["inclusion"], overall_inclusion=overall, anti_lift=anti_lift))
        anti.sort(key=lambda a: a["anti_lift"])
        return anti

    def _compute_exclusive(
        self,
        top_entries: list[ResultEntry],
        normalized_cards: list[str],
        n_matching: int,
    ) -> list[ExclusiveEntry]:
        spec_decks = [self.inverted.get(c, set()) for c in normalized_cards]
        exclusive: list[ExclusiveEntry] = []
        for e in top_entries:
            r_decks = self.inverted.get(e["name"], set())
            single_incs = [
                len(r_decks & sd) / len(sd)
                for sd in spec_decks
                if len(sd) > 0
            ]
            if not single_incs:
                continue
            max_single = max(single_incs)
            if max_single == 0:
                continue
            exclusive.append(ExclusiveEntry(name=e["name"], inclusion=e["inclusion"], max_single_inclusion=max_single, exclusivity=e["inclusion"] / max_single))
        exclusive.sort(key=lambda x: x["exclusivity"], reverse=True)
        return exclusive


def _compute_consensus(matching: set[int], all_decks: list[set[str]]) -> float:
    deck_list = list(matching)
    n = len(deck_list)
    if n < 2:
        return 1.0 if n == 1 else 0.0
    all_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    pairs = random.sample(all_pairs, CONSENSUS_SAMPLE_PAIRS) if len(all_pairs) > CONSENSUS_SAMPLE_PAIRS else all_pairs
    total = 0.0
    for i, j in pairs:
        a, b = all_decks[deck_list[i]], all_decks[deck_list[j]]
        union = len(a | b)
        total += len(a & b) / union if union else 0.0
    return total / len(pairs)


def _find_packages(
    top_entries: list[ResultEntry],
    matching: set[int],
    all_decks: list[set[str]],
    n_matching: int,
) -> list[PackageEntry]:
    if len(top_entries) < 2 or n_matching == 0:
        return []
    cards = [e["name"] for e in top_entries]
    inc = {e["name"]: e["inclusion"] for e in top_entries}
    card_decks = {card: {idx for idx in matching if card in all_decks[idx]} for card in cards}

    adj: dict[str, list[str]] = defaultdict(list)
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            a, b = cards[i], cards[j]
            p_ab = len(card_decks[a] & card_decks[b]) / n_matching
            denom = inc[a] * inc[b]
            if denom > 0 and p_ab / denom >= PACKAGE_LIFT_THRESHOLD:
                adj[a].append(b)
                adj[b].append(a)

    visited: set[str] = set()
    packages: list[PackageEntry] = []
    for start in cards:
        if start in visited or start not in adj:
            continue
        component: list[str] = []
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            queue.extend(adj[node])
        if MIN_PACKAGE_SIZE <= len(component) <= MAX_PACKAGE_SIZE:
            lifts = []
            for i in range(len(component)):
                for j in range(i + 1, len(component)):
                    a, b = component[i], component[j]
                    p_ab = len(card_decks[a] & card_decks[b]) / n_matching
                    denom = inc[a] * inc[b]
                    if denom > 0:
                        lifts.append(p_ab / denom)
            packages.append(PackageEntry(
                cards=sorted(component),
                avg_lift=sum(lifts) / len(lifts) if lifts else 0.0,
                avg_inclusion=sum(inc[c] for c in component) / len(component),
            ))

    packages.sort(key=lambda p: p["avg_lift"], reverse=True)
    return packages


# Global singleton
deck_index = DeckIndex()
