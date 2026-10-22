# Traffic scene generator — input milestone

Completed 2026-10-22. The [frozen v1 recipe](TRAFFIC_RELIABILITY_PROTOCOL.md)
is now implemented as a separate, experiment-only generator. **No tracker
comparison, held-out tracking outcome, real camera validation or improvement
claim is included in this milestone.** The frozen recipe and its lock are unchanged.

## What this means without the technical terms

Imagine a person following the same straight path four times. We keep the true
path exactly the same, but change what the camera measurement looks like:

1. Clean boxes with a simple projection.
2. A perspective projection, where equal movement on the ground can appear
   faster or slower at different parts of the image, with changing box size.
3. The simple projection with small box-edge jitter and two imposed box cuts.
4. Perspective and box errors together.

These are numeric toy objects, not recordings or realistic rendered people.
Perspective changes apparent speed **and** scale jointly. The camera is static.
The imposed box errors are not measurements of an actual detector.

The generator keeps the correct answer separate from the imperfect measurement.
That lets us later ask whether the unchanged tracker loses an object or produces
a wrong counting event. It does not answer that question yet.

## Implemented and checked

- Only registered split/scenario/seed/condition combinations are accepted, after
  the byte-level protocol integrity check. The generator writes no files,
  constructs no tracker and accesses no camera, network or dataset.
- True world paths, projected contacts, ideal boxes and observed boxes remain
  separate. IDs describe reference objects, not known people or detector inputs.
- Four edge-noise draws per object/frame are consumed in the registered order,
  including in clean conditions. Paired conditions share the same paths and
  draws; local generation does not modify NumPy's global random state.
- Box error uses ideal dimensions. The bottom cut applies on frames 135–164,
  and the top cut on frames 210–239. Neither changes the true path. A bottom cut
  shifts the bottom anchor and centre; a top cut shifts the centre but not the
  bottom anchor apart from the independently imposed jitter.
- Projection/inverse checks reject singular transforms, nonfinite inputs and
  invalid homogeneous denominators near the projection horizon. Boxes must
  have positive dimensions and remain in the image. Nothing is clipped or
  silently discarded to make an invalid scene pass.
- Valid inverse-projected measurements outside the ground ROI remain outside
  it. They are not clamped into valid counting positions.
- Generated arrays have immutable byte backing. Repeated generation is
  byte-identical in the tested environment; manifests include the NumPy version.
  Every one of the 120 registered **development** input combinations has a
  validity test. This is input verification, not 120 tracker evaluations.

The generator is
[`experiments/traffic_scene.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/traffic_scene.py).
Its tests are
[`tests/test_traffic_scene.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/tests/test_traffic_scene.py).
It does not modify `src/visiontrack/detection/synthetic.py`, the public tracking
API, the live website, or Python/C++ parity fixtures.

## Technical input contract

All numeric arrays use float64. With F=300 frames and N=1 or 2 reference objects,
the fields are:

| Fields | Shape / meaning |
| --- | --- |
| `frames`, `timestamps` | F; frame index and seconds at 30 fps |
| `object_ids` | Sorted reference ID tuple; no identity feature |
| `world_contacts`, `pixel_contacts` | F×N×2; true contacts in two coordinate systems |
| `ideal_boxes` | F×N×4; unperturbed sprite boxes, x1/y1/x2/y2 |
| `ideal_box_centres` | F×N×2; separate from ground contacts |
| `edge_draws` | F×N×4; common PCG64 draws before condition-dependent error |
| `observed_boxes` | F×N×4; eventual detector-box inputs, not tracker outputs |
| `observed_bottom_centres`, `observed_box_centres` | F×N×2; imperfect image anchors |
| `observed_bottom_world`, `observed_centre_world` | F×N×2; anchors inverse-projected with exact H |

`generate_scene(split=..., scenario=..., seed=..., condition=...)` returns
`SceneInputs`; there is no default split or arbitrary configuration override.
The module has no tracker runner or export command. For development verification
from the repository root:

```sh
python -m experiments.traffic_protocol
python -m pytest tests/test_traffic_scene.py tests/test_traffic_protocol.py
```

`SceneInputs.manifest()` returns a fresh JSON-safe dictionary with recipe/doc
hashes, registered run identifiers, NumPy version and SHA-256 digests for world
truth, ideal truth, random draws and observations. The whole input manifest is
also hashed. World truth and draws agree across all four paired conditions;
ideal truth agrees within the same projection. Observations differ as specified.

Array digests use named/shape-tagged little-endian C-order float64 bytes. Each
JSON header and byte payload is prefixed by its 8-byte little-endian length;
the format has a versioned domain prefix. The combined digest uses sorted,
compact JSON without nonfinite constants, before adding `input_sha256` itself.
Integrity checks and replay checks are not accuracy measurements. Exact bytes
can depend on numerical-library/environment versions; cross-environment changes
must be disclosed, not treated as new evidence or silently re-frozen.

## What comes next

1. The frozen crossing-event scorer is now implemented and tested on
   [hand-checked fixtures](TRAFFIC_RELIABILITY_SCORER.md), without tracker runs.
2. The [development-only replay adapter](TRAFFIC_RELIABILITY_RUNNER.md) now
   verifies the pinned source/configuration, reference-free detector inputs and
   reset/fresh equality, recording provenance, input/output digests and crossing
   scores. It is not yet the complete study report.
3. The [tracking/contact diagnostics](TRAFFIC_RELIABILITY_DIAGNOSTICS.md) now
   implement the region/pulse strata with missing estimates kept explicit.
   Complete result exports and paired development summaries remain next,
   including unfavorable results.
4. Freeze the complete tested harness revision and input digests **before** the
   one-pass held-out tracker evaluation. No intervention tuning is part of v1.

RQ5 re-entry/consented recording remains a separate study. C++ stays on the
existing runtime contract. No new recording, email response, upload or other
owner action is needed for the next implementation step.
