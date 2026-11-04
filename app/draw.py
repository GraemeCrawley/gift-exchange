import random
from collections import Counter

MAX_STEPS = 10_000


class DrawImpossible(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _allowed(giver_house: str | None, receiver_house: str | None) -> bool:
    return giver_house is None or receiver_house is None or giver_house != receiver_house


def make_draw(people: list[tuple[int, str | None]], rng: random.Random | None = None) -> dict[int, int]:
    """Return {giver_id: receiver_id}: nobody draws themselves or their own household."""
    rng = rng or random.SystemRandom()
    n = len(people)
    if n < 3:
        raise DrawImpossible("You need at least 3 people to draw names.")

    sizes = Counter(h for _, h in people if h is not None)
    for house, size in sizes.items():
        if size > n / 2:
            raise DrawImpossible(
                f"Can't draw: Household {house} has too many people for this group. "
                "Move someone out of it or add more people."
            )

    house = dict(people)
    givers = [p for p, _ in people]
    rng.shuffle(givers)
    result: dict[int, int] = {}
    taken: set[int] = set()
    steps = 0

    def solve(i: int) -> bool:
        nonlocal steps
        if i == len(givers):
            return True
        g = givers[i]
        options = [r for r in house if r != g and r not in taken and _allowed(house[g], house[r])]
        rng.shuffle(options)
        for r in options:
            steps += 1
            if steps > MAX_STEPS:
                return False
            result[g] = r
            taken.add(r)
            if solve(i + 1):
                return True
            taken.discard(r)
            del result[g]
        return False

    if not solve(0):
        raise DrawImpossible("Couldn't find a valid draw with these households. Try changing the households.")
    return result
