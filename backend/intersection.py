from typing import TypedDict


class ResultEntry(TypedDict):
    name: str
    inclusion: float
    num_decks: int
    source: str
