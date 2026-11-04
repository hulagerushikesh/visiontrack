# Inspect longer recordings without loading every saved row

## Bounded active history — checkout, 2026-11-04

The next engineering step removes the remaining per-match history growth from
the **Lab diagnostic replay**. This is implemented in the checkout, not in the
published 0.5.1 artifacts described below. The ordinary `ByteTracker()` still
keeps full public history; callers can explicitly select
[`history_limit`](API.md#optional-history-retention-checkout-only-not-published-in-051).

The history audit found two built-in consumers: momentum reads the last box and
the box `ocm_delta_t` matched observations earlier; the learned residual uses five
velocities, requiring six boxes. Replays retain `max(6, ocm_delta_t + 1)` boxes
per active track. Residual inference also constructs centers only from its six
required boxes, including when full history is retained. Matching, Kalman
arithmetic, lifecycle and returned observations are unchanged. This preserves
the existing matched-observation semantics; it does not reinterpret gaps as
equally spaced video frames or change the motion method.

Two generated probes use Python 3.12.9 / NumPy 2.5.4 on macOS ARM64:

| Probe | Full-history peak | Limited-history peak | Evidence |
| --- | --- | --- | --- |
| Direct tracker, 1,000 frames | 307,456 bytes | 28,624 bytes | 998 returned observations, exact SHA |
| Direct tracker, 10,000 frames | 2,831,776 bytes | 28,624 bytes | 9,998 returned observations, exact SHA |
| Initiation replay, 6,000 frames | 2,950,096 bytes | 1,266,508 bytes | Exact diagnostic content against published 0.5.1 |
| Association replay, 6,000 frames | 2,951,346 bytes | 1,267,186 bytes | Exact diagnostic content against published 0.5.1 |

These are single-run Python `tracemalloc` peaks, **not total RSS, speed or
accuracy claims**. The direct probe streams one continuously matched generated
object without accumulating output; the bounded track retains six boxes at both
lengths. Replays use the same fixed-box input construction as the historical
probe, check the entire saved output SHA, keep bundles byte-identical and
compare all diagnostic content except actual producer metadata and its dependent
ID. Producer hashes remain intact. Both 600-frame replay checks also pass.
At 6,000 frames, the complete diagnostics use approximately **57% less peak
traced allocation than published 0.5.1**. Fixed producer hashing and serialization
costs remain in this end-to-end figure.

Per-track retained history is bounded by the selected limit. Total memory still
depends on active-track count, feature dimensions, input-frame size and the
selected diagnostic window. Ordinary comparison/metric runners still
materialize their data. This does not solve arbitrary-scale storage or establish
representative traffic accuracy. Default histories, schemas, historical exports,
accepted C++ behavior and published packages are unchanged.

Reproduce with a fresh output directory for each command. Use an isolated public
0.5.1 installation and a checkout interpreter with matching Python/NumPy; the
replay probe refuses a version mismatch rather than reporting a comparison:

```bash
python experiments/track_history_memory.py \
  --output ../visiontrack-walkthrough/my-history-probe
python experiments/diagnostic_replay_memory.py \
  --baseline-python /path/to/public-051/bin/python \
  --baseline-version 0.5.1 \
  --output ../visiontrack-walkthrough/my-history-replay-probe
```

Both scripts retain allocation counts, environment/source identity and exact
output hashes outside Git. Regression checks cover all six presets, combined
appearance/uncertainty/momentum/re-update/camera/residual options, longer momentum
windows, short histories, gaps, expiry, reset, full-history inspection and
refusal of insufficient retention. A full-history residual reference preserves
the pre-optimization calculation for exact numerical comparison.

## Published streaming implementation — 0.5.1

[Published 0.5.1](RELEASE_NOTES_0.5.1.md) streams the saved inputs used by
`lab-initiation` and `lab-association`. Public 0.5.0 retains the earlier
materialized replay.
Commands, v1 JSON structures, tracker settings and arithmetic are unchanged.
The correction is delivered in 0.5.1; C++ behavior is unchanged.

Previously, explaining even one frame loaded all detections, optional reference
labels and saved observations, grouped the complete recording, and accumulated
all replay outputs before hashing them. That duplicated data unrelated to the
small explanation the user requested.

The new path validates saved observations and reference labels one row at a
time, passes one detection frame to the real tracker, and incrementally hashes
canonical public output. It still replays the **whole experiment**, including
warm-up and frames after the selected window. Earlier state is never reset just
to make an explanation cheaper.

## Measured result — 2026-11-01

One synthetic development probe uses two detector rows per frame (scores 0.9
and 0.05), one continuously observed object, a reference row per frame and the
unchanged default tracker. Initiation selects the last two frames; association
selects the last frame, track 1 and original detection key 7. Both processes use
Python 3.12.9 and NumPy 2.5.4 on the same macOS ARM64 machine. The baseline is a
separate non-editable installation of the published 0.5.0 wheel.

| Frames | Diagnostic | Published 0.5.0 peak | Streaming peak | Reduction |
| --- | --- | --- | --- | --- |
| 600 | Initiation | 1,811,892 bytes | 1,186,909 bytes | 34.5% |
| 600 | Association | 1,810,314 bytes | 1,153,540 bytes | 36.3% |
| 6,000 | Initiation | 13,995,403 bytes | 2,923,822 bytes | 79.1% |
| 6,000 | Association | 13,995,755 bytes | 2,923,474 bytes | 79.1% |

These are single-run **Python `tracemalloc` allocation peaks**, not total process
RSS, a statistical benchmark or a speed guarantee. Setup is outside measurement;
each diagnostic includes verification, replay and producer-source hashing.
Instrumented elapsed times are retained in the receipt but do not establish a
speedup. Extra streamed hash passes deliberately retain integrity checks.

Every explanation field agrees exactly with the published implementation after
excluding executing `producer` metadata and its dependent content ID. The actual
producer hashes are retained separately; they are not overwritten to manufacture
identical IDs. The saved input bundles remain byte-identical after all four
diagnostic pairs. Original browser lesson exports and frozen conformance vectors
are unchanged.

## Integrity and limits

- A shared reader checks ordering, duplicate row keys, record shape and frame bounds.
  It hashes the exact consumed bytes beneath UTF-8/newline decoding, preserving
  LF, CRLF, CR and a final row without a newline.
- Detection rows before and after the experiment are also validated. A small
  selected window cannot hide a damaged tail. Optional reference labels remain
  checked even though these diagnostics do not score them.
- Saved track counts, frame ranges, run/configuration lineage and the complete
  replay output SHA must agree. Every input/manifest hash is checked again
  before return; changed or missing evidence refuses the result. CLI errors emit
  no partial JSON. This is reproducibility checking, not producer authentication.
- Working storage includes the largest input row/frame, tracker state, selected
  trace (at most 200 frames / 20,000 rows) and small serialization buffers.
  **The existing tracker keeps the full history of each active track.** A
  long-lived object therefore still causes growth, visible in this probe. This
  change does not claim bounded total tracker memory or infinite recordings.
- The ordinary comparison runner, metrics/report producers and browser imports
  retain their existing materialized inputs and limits. This is specifically the
  read-only diagnostic replay path; full-run replay time still grows with length.
- No detector inference, media access, default change, tracking gain or new
  representative traffic evidence follows from this engineering improvement.

## Reproduce

Use the repository checkout and a separate published baseline with matching
Python and NumPy versions. For the recorded environment, the baseline NumPy is
2.5.4; use that version in the checkout environment too. Keep outputs outside Git
and choose a fresh directory:

```bash
python3 -m venv /tmp/visiontrack-baseline-050
/tmp/visiontrack-baseline-050/bin/python -m pip install \
  "visiontrack-mot[lab]==0.5.0" "numpy==2.5.4"
python experiments/diagnostic_replay_memory.py \
  --baseline-python /tmp/visiontrack-baseline-050/bin/python \
  --output ../visiontrack-walkthrough/my-streaming-probe
```

The [probe source](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/diagnostic_replay_memory.py)
creates only synthetic local bundles. It refuses an existing output folder, an
editable/non-0.5.0 baseline, differing Python/NumPy versions and diagnostic
content differences. `comparison.json` and both producer receipts retain exact
allocation counts, semantic hashes, package source hashes and unchanged-input
checks. No dataset or network access is used by the measurement itself.

Normal CI covers streamed reader memory at 100 versus 10,000 rows, legacy line
endings, gaps, nonzero experiment starts, source tails, invalid/rehashed rows,
saved-output corruption and evidence changed during replay. Existing lifecycle,
association, browser conformance and clean wheel/source installation checks
remain required. Browser interaction and practitioner comprehension are separate
open gates.

Local verification at this checkpoint: **1,324 Python tests pass**, with three
skips and one slow test deselected; all thirteen web contracts/workflows,
TypeScript, production app build, strict documentation, Ruff and canonical
tracker parity/reset pass. Separate clean wheel/source core and Lab installs
pass both Python-to-browser diagnostic workflows. These checkout builds are
verification artifacts, not new published 0.5.0 files.
