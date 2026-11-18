"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError(f"length mismatch: human={len(human)} judge={len(judge)}")
    tp = fp = fn = tn = 0
    for h, j in zip(human, judge):
        h_pos, j_pos = h == POS, j == POS
        if h_pos and j_pos:
            tp += 1
        elif j_pos:
            fp += 1
        elif h_pos:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """precision = tp/(tp+fp), recall = tp/(tp+fn); 0.0 when the denominator is 0."""
    cm = confusion(human, judge)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa undefined: no rows")
    p_o = (cm["tp"] + cm["tn"]) / n
    human_pos = (cm["tp"] + cm["fn"]) / n
    judge_pos = (cm["tp"] + cm["fp"]) / n
    p_e = human_pos * judge_pos + (1 - human_pos) * (1 - judge_pos)
    if p_e == 1:
        raise ValueError("kappa undefined: chance agreement is 1 (constant labels)")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1].
    sens + spec <= 1 means the judge is no better than chance: the correction is undefined (nan)."""
    denom = sensitivity + specificity - 1
    if denom <= 0:
        return float("nan")
    corrected = (observed_rate + specificity - 1) / denom
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy import stats as sps

    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if x.shape != y.shape:
        raise ValueError(f"paired samples need the same items: {x.shape} vs {y.shape}")
    if x.size == 0:
        raise ValueError("paired_bootstrap: no items")
    if np.array_equal(x, y):
        return 0.0, 0.0, 0.0    # zero difference everywhere: a degenerate bootstrap has no spread

    def diff_of_means(u, v, axis=-1):
        return np.mean(u, axis=axis) - np.mean(v, axis=axis)

    res = sps.bootstrap((x, y), diff_of_means, paired=True, vectorized=True, n_resamples=n_resamples,
                        confidence_level=confidence, method="percentile", rng=np.random.default_rng(rng))
    ci = res.confidence_interval
    return float(x.mean() - y.mean()), float(ci.low), float(ci.high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    # TODO M6
    raise NotImplementedError


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    # TODO M6
    raise NotImplementedError
