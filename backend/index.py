from collections import defaultdict
from intersection import ResultEntry


class DeckIndex:
    def __init__(self) -> None:
        self.decks: list[set[str]] = []
        self.inverted: dict[str, set[int]] = defaultdict(set)

    def build(self, decks: list[set[str]]) -> None:
        self.decks = decks
        self.inverted = defaultdict(set)
        for i, deck in enumerate(decks):
            for card in deck:
                self.inverted[card].add(i)

    @property
    def loaded(self) -> bool:
        return len(self.decks) > 0

    def query(self, cards: list[str]) -> list[ResultEntry]:
        normalized = [c.lower() for c in cards]

        if not normalized or not self.loaded:
            return []

        # Find deck indices containing ALL input cards
        matching: set[int] = self.inverted.get(normalized[0], set()).copy()
        for card in normalized[1:]:
            matching &= self.inverted.get(card, set())

        if not matching:
            return []

        # Count co-occurrences across matching decks
        counts: dict[str, int] = defaultdict(int)
        input_set = set(normalized)
        for idx in matching:
            for card in self.decks[idx]:
                if card not in input_set:
                    counts[card] += 1

        total = len(matching)
        results: list[ResultEntry] = [
            {"name": card, "inclusion": count / total, "num_decks": count, "source": "archidekt"}
            for card, count in counts.items()
        ]
        results.sort(key=lambda r: r["inclusion"], reverse=True)
        return results


# Global singleton
deck_index = DeckIndex()
