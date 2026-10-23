"""Read-only audit of the retained DEV trace, never another tracker replay.

Checks trace/output lineage and recorded gate/assignment arithmetic, not Kalman
filter arithmetic or independently witnessed execution. No held-out data entry.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

from experiments.box_gate_audit import git, sealed
from experiments.box_gate_combined_audit import (
    Evidence,
    canonical,
    check,
    decode,
    grid,
    same,
    sha,
    write_output,
)

REVISION = "dd653aaacde96e33ddb647c72521478507f6ae7a"
MANIFEST = "257a7032f614a525606541017699e29347e7ea29172205ee657b4ea28a208a42"
STAGES = ("confirmed_high", "confirmed_low_recovery", "tentative_leftover_high")
MAX_BYTES = 64 * 1024 * 1024


class TraceFiles:
    def __init__(self):
        self.hashes = {}

    def raw(self, path):
        check(path.is_file() and not path.is_symlink(), "regular trace file required")
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        check(len(raw) <= MAX_BYTES, "oversized trace file")
        digest = sha(raw)
        if path in self.hashes:
            same(digest, self.hashes[path], "trace changed during audit")
        self.hashes[path] = digest
        return raw

    def load(self, path):
        return decode(self.raw(path))

    def unchanged(self):
        for path, digest in list(self.hashes.items()):
            same(sha(self.raw(path)), digest, "trace changed during audit")


def frames_for(times):
    result = set(range(4)) | set(range(133, 168)) | set(range(208, 243))
    for time in times:
        check(type(time) in (int, float) and math.isfinite(time) and 0 <= time <= 299,
              "invalid saved crossing time")
        result.update(range(max(0, math.floor(time) - 1), min(300, math.floor(time) + 3)))
    check(len(result) <= 128, "trace selection budget")
    return sorted(result)


def matrix(value, rows, columns, *, boolean=False):
    check(type(value) is list and len(value) == rows, "matrix row count")
    for row in value:
        check(type(row) is list and len(row) == columns, "matrix column count")
        for item in row:
            check(type(item) is bool if boolean else
                  type(item) in (int, float) and math.isfinite(item), "matrix value type")
    return value


def association(event, build, assignment, stage, gate_on):
    """Audit the actual recorded mask/cost/proposals; no new association solver."""
    before, matrices = event["before"], event["matrices"]
    same(before["stage"], stage, "stage order")
    same(before["gate_requested"], stage != STAGES[1], "stage hard-gate request")
    threshold = 0.5 if stage == STAGES[1] else 0.3
    same(before["iou_threshold"], threshold, "stage IoU threshold")
    tracks, ordinals = before["tracks"], before["detection_ordinals"]
    t, d = len(tracks), len(ordinals)
    check(t <= 32 and d <= 32 and len(set(ordinals)) == d, "candidate dimensions")
    if not t or not d:
        same([build, assignment], [None, None], "empty stage has no cost/solver call")
        same(list(matrices.values()), [None] * 4, "empty stage matrices")
        same(event["matches"], [], "empty stage match")
        same(event["unmatched_tracks"], list(range(t)), "empty unmatched tracks")
        same(event["unmatched_detections"], list(range(d)), "empty unmatched detections")
        same([event["gate_threshold"], event["max_cost"]], [None, None], "empty thresholds")
        return []
    check(build is not None and assignment is not None, "missing cost/solver observation")
    ious = matrix(matrices["ious"], t, d)
    classes = matrix(matrices["class_mismatch"], t, d, boolean=True)
    costs = matrix(matrices["cost"], t, d)
    mask = matrix(build["forbidden"], t, d, boolean=True)
    active = gate_on and stage != STAGES[1]
    distance = matrix(matrices["gating_d2"], t, d) if active else None
    same(event["gate_threshold"], 9.4877 if active else None, "active 4D threshold")
    if not active:
        same(matrices["gating_d2"], None, "inactive distance stays null, not zero")
    maximum = 1.0 - threshold
    same(event["max_cost"], maximum, "maximum cost")
    same(build["max_cost"], maximum, "builder maximum cost")
    same(build["cost"], costs, "actual builder cost retained")
    vetoes = []
    for r in range(t):
        for c in range(d):
            overlap = ious[r][c]
            check(0 <= overlap <= 1, "IoU outside unit interval")
            gate_bad = active and distance[r][c] > event["gate_threshold"]
            forbidden = overlap < threshold or classes[r][c] or gate_bad
            same(mask[r][c], forbidden, "recorded forbidden mask")
            same(costs[r][c], maximum + 1.0 if forbidden else 1.0 - overlap,
                 "recorded default weighted cost")
            if gate_bad and overlap >= threshold and not classes[r][c]:
                vetoes.append(dict(frame=event["frame"], stage=stage,
                                   track_id=tracks[r]["track_id"],
                                   detection_ordinal=ordinals[c], iou=overlap,
                                   gating_d2=distance[r][c], threshold=event["gate_threshold"]))
    rows, columns = assignment["proposed_rows"], assignment["proposed_columns"]
    check(type(rows) is list and type(columns) is list, "solver proposals required")
    check(len(rows) == len(columns) == min(t, d), "proposal count")
    for values, bound in ((rows, t), (columns, d)):
        check(all(type(v) is int and 0 <= v < bound for v in values)
              and len(set(values)) == len(values), "proposal bounds/uniqueness")
    accepted = [[r, c] for r, c in zip(rows, columns, strict=True) if costs[r][c] <= maximum]
    same(event["matches"], accepted, "accepted assignments from actual proposals")
    same(event["unmatched_tracks"], [r for r in range(t) if r not in {a[0] for a in accepted}],
         "unmatched tracks")
    same(event["unmatched_detections"], [c for c in range(d) if c not in {a[1] for a in accepted}],
         "unmatched detections")
    return vetoes


def inspect_trace(diagnostic, saved, frames):
    same(diagnostic["format"], "visiontrack.box-gate-internal-trace/v1", "trace format")
    same(diagnostic["public_output"], saved["output"], "complete saved-output parity")
    same(diagnostic["settings"], saved["config"], "saved settings")
    for key in ("expected_output_sha256", "actual_output_sha256"):
        same(diagnostic[key], sha(canonical(saved["output"])), "output bytes hash")
    same(diagnostic["exact_public_output_parity"], True, "parity flag")
    same(diagnostic["selected_frames"], frames, "fixed selection")
    for name in ("provenance_verified", "interpretation_allowed", "validation_evidence"):
        same(diagnostic[name], False, "observer does not authorize itself")
    current, stage, build, assignment = None, 0, None, None
    seen, vetoes = [], []
    public = {}
    for row in saved["output"]:
        public.setdefault(row["frame"], []).append(row)
    for event in diagnostic["events"]:
        kind = event["kind"]
        if kind == "frame_start":
            check(current is None and len(seen) < len(frames), "overlapping trace frame")
            same(event["frame"], frames[len(seen)], "selected frame order")
            current, stage = event["frame"], 0
            seen.append(current)
        check(current is not None and event["frame"] == current, "event frame scope")
        if kind == "cost_build":
            check(build is None and assignment is None, "duplicate cost observation")
            build = event
        elif kind == "assignment":
            check(build is not None and assignment is None, "solver call order")
            assignment = event
        elif kind == "association":
            check(stage < 3, "extra association stage")
            vetoes.extend(association(event, build, assignment, STAGES[stage],
                                      saved["config"]["use_mahalanobis_gating"]))
            stage += 1
            build, assignment = None, None
        elif kind == "frame_end":
            same(stage, 3, "three complete stages required")
            same([build, assignment], [None, None], "unconsumed cost/solver observation")
            expected = public.get(current, [])
            same(event["public_output"], expected, "selected frame public output")
            published = [dict(frame=current, track_id=t["track_id"], xyxy=t["xyxy"],
                              score=t["score"], class_id=t["class_id"])
                         for t in event["tracks"]
                         if t["state"] == "CONFIRMED" and t["time_since_update"] == 0]
            same(published, expected, "public-output lifecycle eligibility")
            current = None
        else:
            check(kind in ("frame_start", "_predict_all", "_apply_match", "_spawn", "mark_missed"),
                  "unexpected trace event")
    same(current, None, "unterminated trace frame")
    same(seen, frames, "complete selected frames")
    return dict(selected_frames=len(frames), associations=3 * len(frames),
                gate_only_forbidden_candidate_pairs=vetoes)


def audit(bundle, development, root):
    evidence, traces = Evidence(), TraceFiles()
    auditor_sha256 = sha(traces.raw(Path(__file__).resolve()))
    index = evidence.index(root, "development")
    spec = evidence.load(root / "experiments/box_gate_protocol_v1.json")
    parent = evidence.load(root / "experiments/traffic_protocol_v1.json")
    for name, digest in index["protocol_hashes"].items():
        same(sha(evidence.bytes(root / name)), digest, "original protocol bytes")
    original, original_plan = evidence.bundle(development, index, spec, parent, "development")
    manifest = traces.load(bundle / "manifest.json")
    sealed(manifest, "manifest_sha256")
    same(manifest["manifest_sha256"], MANIFEST, "exact completed trace run required")
    same([manifest[k] for k in ("status", "attempted_variants", "completed_variants",
                               "unattempted_variants", "error")],
         ["complete", 240, 240, 0, None], "complete run")
    same(manifest["exploratory_interpretation_allowed"], True, "complete manifest permission")
    for name in ("heldout_files_read", "is_original_registered_execution",
                 "validation_evidence", "production_change_authorized"):
        same(manifest[name], False, "diagnostic scope")
    files = {"plan.json"} | {f"{directory}/{i:03d}.json" for i in range(1, 241)
                             for directory in ("attempts", "traces")}
    same(sorted(manifest["files_sha256"]), sorted(files), "exact trace inventory")
    Evidence.coverage(bundle, files | {"manifest.json"})
    for name, digest in manifest["files_sha256"].items():
        same(sha(traces.raw(bundle / name)), digest, "trace file hash")
    plan = traces.load(bundle / "plan.json")
    same(plan["diagnostic_state"], manifest["diagnostic_state"], "run source/runtime")
    same(plan["diagnostic_state"]["source"]["actual_revision"], REVISION, "committed harness")
    same(plan["diagnostic_state"]["source"]["worktree_dirty"], False, "clean harness")
    same(plan["diagnostic_state"]["environment"], index["environment"], "recorded runtime")
    for name, digest in plan["code_sha256"].items():
        same(sha(git(root, "show", f"{REVISION}:{name}")), digest, "historical diagnostic code")
    for record in (manifest, plan):
        same(record["original_development_manifest_sha256"], original["manifest_sha256"],
             "original development lineage")
    same(len(plan["cases"]), 120, "complete trace plan")
    cases = []
    for position, (scenario, seed, condition) in enumerate(grid(spec, parent, "development")):
        selector = dict(scenario=scenario, seed=seed, condition=condition)
        saved = [evidence.load(development / f"pairs/{scenario}/{seed}/{condition}/{v}.json")
                 for v in ("baseline", "gate_off")]
        times = [e["frame_time"] for s in saved for e in
                 s["scoring"]["crossing"]["bottom_centre"]["predicted_events"]]
        frames = frames_for(times)
        expected_plan = dict(selector=selector, frames=frames,
                             input_sha256=original_plan["inputs"][position]["input_sha256"],
                             expected_outputs={s["id"]: s["output_sha256"] for s in saved})
        same(plan["cases"][position], expected_plan, "fixed original case plan")
        summaries = {}
        for offset, record in enumerate(saved):
            number = 2 * position + offset + 1
            attempt = traces.load(bundle / f"attempts/{number:03d}.json")
            same(attempt, dict(status="started", **selector, variant=record["id"]), "attempt order")
            result = traces.load(bundle / f"traces/{number:03d}.json")
            for name, expected in (("selector", selector), ("variant", record["id"]),
                                   ("saved_input_sha256", expected_plan["input_sha256"]),
                                   ("saved_output_sha256", record["output_sha256"]),
                                   ("interpretation_allowed", False)):
                same(result[name], expected, "trace receipt lineage")
            same(result["diagnostic"]["frame_count"], 300, "complete frame count")
            summaries[record["id"]] = inspect_trace(result["diagnostic"], record, frames)
        cases.append(dict(**selector, variants=summaries))
    evidence.unchanged()
    traces.unchanged()
    Evidence.coverage(bundle, files | {"manifest.json"})
    return dict(
        format="visiontrack.box-gate-development-trace-audit/v1", source_revision=REVISION,
        auditor_sha256=auditor_sha256,
        trace_manifest_sha256=MANIFEST, original_manifest_sha256=original["manifest_sha256"],
        verified_trace_files=482, verified_original_files=365, paired_cases=120,
        variants=240, recorded_updates=72000, exact_saved_output_variants=240,
        new_tracker_runs=0, heldout_files_read=False, cases=cases,
        recorded_association_stages=sum(v["associations"] for c in cases
                                        for v in c["variants"].values()),
        baseline_gate_only_forbidden_candidate_pairs=sum(
            len(c["variants"]["baseline"]["gate_only_forbidden_candidate_pairs"]) for c in cases),
        gate_off_gate_only_forbidden_candidate_pairs=sum(
            len(c["variants"]["gate_off"]["gate_only_forbidden_candidate_pairs"]) for c in cases),
        limitations=["Read-only post-run audit, not independently witnessed execution.",
                     "Recorded gate/cost/assignment checked; filter/covariance math not rerun.",
                     "Actual payload receipts trusted; not independently regenerated here.",
                     "Gate-only candidate-pair vetoes are not independent errors/people/trials.",
                     "Development-only exploration; no fresh validation, fix or C++ adoption."],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--development", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.trace, args.development, args.root)
        if args.output:
            digest = write_output(args.output, result,
                                  [args.root, args.trace, args.development.parent])
            print(canonical(dict(output=str(args.output.resolve()), sha256=digest)).decode())
        else:
            print(canonical(result).decode())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"Trace audit refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
