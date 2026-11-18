"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    rows = pr.get("rows") or []
    manifest = pr.get("manifest") or {}

    # 1. NaN / inf metric values
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (NaN/inf is not a result)")

    # 2. row count and duplicates
    want = int(manifest.get("items", 0)) * len(manifest.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {manifest.get('items')} items x "
                        f"{len(manifest.get('seeds') or [])} seeds = {want} (dropped or duplicated rows)")
    keys = [(r["item_id"], r["seed"]) for r in rows]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        problems.append(f"duplicated (item, seed) rows: {dup[:3]}")

    # 3. (item, seed) set must equal the baseline's
    base_keys = {(r["item_id"], r["seed"]) for r in base.get("rows") or []}
    if set(keys) != base_keys:
        gone, extra = sorted(base_keys - set(keys)), sorted(set(keys) - base_keys)
        problems.append(f"(item, seed) set differs from the baseline: {len(gone)} missing {gone[:2]}, "
                        f"{len(extra)} extra {extra[:2]}")

    # 4. crashed graders: evaluator_failures, or a graded metric that is None / absent in a row
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s): {pr['evaluator_failures'][0]}")
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]
    for m in graded:
        bad = [(r["item_id"], r["seed"]) for r in rows if r.get(m) is None]
        if bad:
            problems.append(f"metric {m} is None/absent in {len(bad)} row(s), e.g. {bad[0]} (grader crashed or row edited)")

    # 5. reported metrics must be reproducible from the rows (a hand-edited summary hides the evidence)
    problems += _recompute_mismatch(pr, graded, spec)

    # 6. slice tags must match the baseline's (relabelling an item out of a slice hides it)
    tags = lambda rep: {r["item_id"]: sorted(r.get("slices") or []) for r in rep.get("rows") or []}
    tp, tb = tags(pr), tags(base)
    moved = sorted(i for i in tp if i in tb and tp[i] != tb[i])
    if moved:
        problems.append(f"slice tags differ from the baseline for {len(moved)} item(s), e.g. {moved[0]}: "
                        f"{tb[moved[0]]} -> {tp[moved[0]]}")

    # 7. ratchet: thresholds may only get stricter within the same eval-set version
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems += _ratchet(spec, base_spec)
    return problems


def _recompute_mismatch(pr: dict, graded: list[str], spec: dict) -> list[str]:
    rows = [dict(r) for r in pr.get("rows") or []]
    if not rows or any(r.get(m) is None for r in rows for m in graded):
        return []                                   # already reported above
    has_cost = all("cost" in r for r in rows)
    for r in rows:
        r.setdefault("cost", 0.0)
    try:
        want = aggregate(rows, graded, k_values=spec.get("pass_k", []))
    except (KeyError, TypeError, ValueError):
        return []
    out = []
    for k, w in want.items():
        got = (pr.get("metrics") or {}).get(k)
        if got is None or (k == "cost_per_success" and not has_cost):
            continue
        if not isinstance(got, (int, float)) or w is None or abs(float(got) - float(w)) > 1e-3:
            out.append(f"metric {k} reported {got} but the rows give {w} (summary does not match rows)")
    return out


def _loosened(name: str, th: dict, base_th: dict, out: list[str]) -> None:
    if "max" in base_th and not ("max" in th and th["max"] <= base_th["max"]):
        out.append(f"{name}: max {base_th['max']} -> {th.get('max', 'removed')} (looser)")
    if "min" in base_th and not ("min" in th and th["min"] >= base_th["min"]):
        out.append(f"{name}: min {base_th['min']} -> {th.get('min', 'removed')} (looser)")
    if "max_increase" in base_th and not ("max_increase" in th and th["max_increase"] <= base_th["max_increase"]):
        out.append(f"{name}: max_increase {base_th['max_increase']} -> {th.get('max_increase', 'removed')} (looser)")
    if base_th.get("no_significant_drop") and not th.get("no_significant_drop"):
        out.append(f"{name}: no_significant_drop removed (looser)")


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    out: list[str] = []
    cur = {m["id"]: m for m in spec.get("metrics", [])}
    for bm in base_spec.get("metrics", []):
        m = cur.get(bm["id"])
        if m is None:
            out.append(f"ratchet: metric {bm['id']} disappeared from the spec")
            continue
        if bm.get("blocking") and not m.get("blocking"):
            out.append(f"ratchet: {bm['id']} is no longer blocking")
        _loosened(f"ratchet: {bm['id']}", m.get("threshold") or {}, bm.get("threshold") or {}, out)
    cur_s = {s["name"]: s for s in spec.get("slices") or []}
    for bs in base_spec.get("slices") or []:
        s = cur_s.get(bs["name"])
        if s is None:
            out.append(f"ratchet: slice {bs['name']} disappeared from the spec")
            continue
        if bs.get("blocking") and not s.get("blocking"):
            out.append(f"ratchet: slice {bs['name']} is no longer blocking")
        if bs.get("metric") != s.get("metric"):
            out.append(f"ratchet: slice {bs['name']} metric {bs.get('metric')} -> {s.get('metric')}")
        _loosened(f"ratchet: slice {bs['name']}", s, bs, out)
    b_conf = (base_spec.get("bootstrap") or {}).get("confidence")
    conf = (spec.get("bootstrap") or {}).get("confidence")
    if b_conf is not None and (conf is None or conf < b_conf):
        out.append(f"ratchet: bootstrap confidence {b_conf} -> {conf} (narrower CI blocks less)")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    bs = spec.get("bootstrap", {})
    blocked: list[str] = []
    lines: list[str] = []
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        verdict, note = "ok", ""
        if not a:
            val, verdict = None, "missing"            # slice is empty in the PR: nothing to trust
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in sl and val < sl["min"]:
                verdict = "fail"
            if sl.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if len(keys) >= 2:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        lines.append(f"  {sid:<34} {val!s:<8} n={len(a):<3} {json.dumps(th):<36} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
