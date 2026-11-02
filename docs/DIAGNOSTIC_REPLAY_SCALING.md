# Inspect longer recordings without loading every saved row

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
