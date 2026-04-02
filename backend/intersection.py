from typing import TypedDict


class ResultEntry(TypedDict):
    name: str
    inclusion: float   # fraction of matching decks containing this card
    num_decks: int
    price: float | None


class UniqueEntry(TypedDict):
    name: str
    inclusion: float          # fraction of matching decks
    overall_inclusion: float  # fraction of ALL decks
    lift: float               # inclusion / overall_inclusion
    price: float | None


class PackageEntry(TypedDict):
    cards: list[str]
    avg_lift: float       # average pairwise lift within the package
    avg_inclusion: float  # average inclusion across cards in this package


class AntiCorrelationEntry(TypedDict):
    name: str
    inclusion: float          # fraction of matching decks (low)
    overall_inclusion: float  # fraction of ALL decks (comparatively high)
    anti_lift: float          # < 1.0; lower = more anti-correlated
    price: float | None


class ExclusiveEntry(TypedDict):
    name: str
    inclusion: float              # fraction of all-match decks
    max_single_inclusion: float   # highest inclusion across any single input card's decks
    exclusivity: float            # inclusion / max_single_inclusion; > 1.0 = combo-specific
    price: float | None
