import random

import pytest

from app.draw import DrawImpossible, make_draw


def check_valid(people, result):
    ids = {p for p, _ in people}
    house = dict(people)
    assert set(result) == ids
    assert set(result.values()) == ids
    for g, r in result.items():
        assert g != r
        if house[g] is not None and house[r] is not None:
            assert house[g] != house[r]


def test_no_self_and_bijection():
    people = [(i, None) for i in range(1, 11)]
    for seed in range(200):
        check_valid(people, make_draw(people, random.Random(seed)))


def test_households_respected():
    people = [(1, "A"), (2, "A"), (3, "A"), (4, "B"), (5, "B"), (6, "C"), (7, "C"), (8, None), (9, None)]
    for seed in range(200):
        check_valid(people, make_draw(people, random.Random(seed)))


def test_none_household_is_not_a_group():
    people = [(1, None), (2, None), (3, None)]
    for seed in range(200):
        check_valid(people, make_draw(people, random.Random(seed)))


def test_too_few():
    with pytest.raises(DrawImpossible, match="at least 3"):
        make_draw([(1, None), (2, None)])


def test_impossible_household():
    people = [(1, "A"), (2, "A"), (3, "A"), (4, "A"), (5, "B"), (6, "C")]
    with pytest.raises(DrawImpossible, match="Household A"):
        make_draw(people)


def test_random():
    people = [(i, None) for i in range(1, 7)]
    results = {tuple(sorted(make_draw(people, random.Random(s)).items())) for s in range(50)}
    assert len(results) > 1
