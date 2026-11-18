"""Regression test cho trace case C-008@11 (docs/trace_case.md): FM-08 misreport.

Chạy trong src/:  python -m pytest -q -m student -o addopts= tests/test_lab9_trace_regression.py
Trên `seeded_regression` reply nói số tiền khác ledger, và grader Lab 8 vẫn PASS: chỉ
ReplyMatchesLedger bắt được. Trên `fixed` reply khớp ledger.
"""
import pytest

pytestmark = pytest.mark.student


def _ctx(case):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=case["label"],
                            output=case["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})


@pytest.fixture(scope="module")
def cases():
    from lab9.trace_case import investigate

    return {shape: investigate(shape, "C-008", 11) for shape in ("seeded_regression", "fixed")}


def test_seeded_regression_misreports_amount(cases):
    from lab9.graders import RefundAmountCorrect, ReplyMatchesLedger

    case = cases["seeded_regression"]
    ctx = _ctx(case)
    assert case["trial"]["lab8_pass"] is True                  # grader Lab 8 bỏ sót
    assert RefundAmountCorrect().evaluate(ctx).value is True   # ledger đúng nhãn
    assert ReplyMatchesLedger().evaluate(ctx).value is False   # reply nói số khác ledger


def test_fixed_reply_matches_ledger(cases):
    from lab9.graders import ReplyMatchesLedger

    assert ReplyMatchesLedger().evaluate(_ctx(cases["fixed"])).value is True
