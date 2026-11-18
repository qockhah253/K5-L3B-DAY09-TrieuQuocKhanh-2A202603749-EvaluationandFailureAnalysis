"""Extra M7 checks beyond the public vectors: traps the starter does not build.
Run: python -m pytest -q -m student -o addopts= -k advanced"""
import copy

import pytest

pytestmark = pytest.mark.student

ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": i != 3 or s != 1, "slices": [], "cost": 1.0}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                                               "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "s", "metric": "pass_rate", "min": 0.9, "no_significant_drop": True, "blocking": True}]}


def _rep(rows, value):
    return {"manifest": {"eval_set_sha": "x", "items": 4, "seeds": [1, 2]}, "rows": rows,
            "metrics": {"pass_rate": value}, "evaluator_failures": []}


def test_integrity_flags_duplicated_rows_kept_to_the_same_count():
    from lab9 import gate

    base = _rep(copy.deepcopy(ROWS), 0.875)
    rows = [r for r in copy.deepcopy(ROWS) if not (r["item_id"] == "E-003" and r["seed"] == 1)]
    rows.append(copy.deepcopy(rows[0]))                # same length, a failing row replaced by a copy
    assert gate.integrity_check(_rep(rows, 1.0), base, SPEC)


def test_integrity_flags_hand_edited_summary():
    from lab9 import gate

    base = _rep(copy.deepcopy(ROWS), 0.875)
    assert gate.integrity_check(base, base, SPEC) == []
    assert gate.integrity_check(_rep(copy.deepcopy(ROWS), 0.99), base, SPEC)


def test_integrity_flags_evaluator_failures_on_an_otherwise_green_run():
    from lab9 import gate

    base = _rep(copy.deepcopy(ROWS), 0.875)
    pr = _rep(copy.deepcopy(ROWS), 0.875)
    pr["evaluator_failures"] = ["E-003@1:TrialPass:boom"]
    assert gate.integrity_check(pr, base, SPEC)


def test_integrity_flags_relabelled_slice():
    from lab9 import gate

    base = _rep(copy.deepcopy(ROWS), 0.875)
    for r in base["rows"]:
        r["slices"] = ["s"]
    pr = _rep(copy.deepcopy(ROWS), 0.875)              # same items, slice tag removed
    assert gate.integrity_check(pr, base, SPEC)


@pytest.mark.parametrize("mutate", [
    lambda sp: sp["slices"].clear(),
    lambda sp: sp["metrics"][0].update(blocking=False),
    lambda sp: sp["metrics"][0]["threshold"].pop("no_significant_drop"),
    lambda sp: sp["slices"][0].update(min=0.5),
    lambda sp: sp["metrics"].clear(),
])
def test_integrity_flags_each_way_of_loosening_a_spec(mutate):
    from lab9 import gate

    base = _rep(copy.deepcopy(ROWS), 0.875)
    loose = copy.deepcopy(SPEC)
    mutate(loose)
    assert gate.integrity_check(base, base, loose, SPEC)
    assert gate.integrity_check(base, base, SPEC, SPEC) == []


def test_slice_check_blocks_an_empty_slice():
    from lab9 import gate

    base = _rep(copy.deepcopy(ROWS), 0.875)
    blocked, _ = gate.slice_check(base, base, SPEC)    # nobody carries the tag "s"
    assert blocked == ["slice:s/pass_rate"]
