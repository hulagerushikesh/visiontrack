# VisionTrack cross-runtime tracking contract

Contract ID: `visiontrack.tracker-parity/v1`  
Status: accepted design; executable fixture is the next increment  
Authority: the NumPy implementation defines behavior; the C++ implementation
may optimize only while preserving this contract.

## Purpose

This is the first explicit synchronization boundary between `visiontrack` and
`visiontrack-cpp`. It is deliberately smaller than either repository: it covers
the stable online ByteTrack path needed by the Reliability Lab, not detectors,
video decoding, evaluation, UI, or research-only tracker extensions.

Both repositories will carry the same canonical golden fixture bytes. CI will
reject fixture drift and will compare each runtime's canonical output with the
fixture's expected output.

## Versioned envelope

The executable fixture will be one UTF-8 JSON document with sorted object keys,
compact separators, no NaN or infinity, and a final newline:

```json
{
  "contract_id": "visiontrack.tracker-parity/v1",
  "config": {},
  "frames": [],
  "expected_observations": []
}
```

Unknown top-level or record fields are rejected. A behavioral or structural
breaking change requires `/v2`; adding a new independent fixture does not.

## Canonical input

Each item in `frames` has:

- `frame_index`: contiguous, zero-based integer in feed order;
- `detections`: an ordered list of records containing `xyxy`, `score`,
  `class_id`, and optional `feature`;
- `xyxy`: four finite float64 values `[x1, y1, x2, y2]` in continuous pixel
  coordinates, with `x2 >= x1` and `y2 >= y1`; width is `x2 - x1` and height is
  `y2 - y1`—there is no inclusive-pixel `+1` convention;
- `score`: a finite float64 confidence;
- `class_id`: an integer, where `-1` is class-agnostic;
- `feature`: when present, a finite float64 vector with one consistent,
  non-zero dimension throughout the sequence.

Detection order is part of the input because equal-cost assignment ties may be
order-sensitive. Each runtime must reset before a fixture and must receive one
`update` call for every frame, including empty frames.

`config` contains only the stable intersection:

`high_score_thresh`, `low_score_thresh`, `match_iou_thresh`,
`recovery_iou_thresh`, `new_track_thresh`, `n_init`, `max_age`,
`use_mahalanobis_gating`, `class_aware`, `w_iou`, `w_app`, `w_unc`,
`use_giou`, `appearance_ema_alpha`, and `kf_noise_scale`.

`use_lapjv`, GMC, OC-SORT/ORU, observation-centric momentum, and learned motion
residuals are outside v1. A runtime must reject an unsupported request rather
than silently ignore it.

## Lifecycle semantics

- IDs start at 1, increase monotonically, and reset to 1 with a new tracker.
- A new track starts tentative with `hits = 1`; creation counts as its first hit.
- It becomes confirmed when a matched update makes `hits >= n_init`.
- A tentative track is deleted on its first unmatched frame.
- Prediction increments `time_since_update` before association.
- A confirmed track survives `max_age` complete unmatched frames and is deleted
  when `time_since_update > max_age`.
- Only confirmed tracks matched on the current frame are emitted. Coasting
  predictions are internal and are not output observations.
- Surviving track order is preserved; newly spawned tracks append. Output order
  follows that stable track order and is therefore contract-significant.

## Canonical output

`expected_observations` is a list ordered first by `frame_index` and then by the
runtime's stable track order. Every record contains exactly:

- `frame_index`: zero-based integer;
- `track_id`: positive integer;
- `xyxy`: four float64 values after Kalman correction;
- `score`: the most recently matched detection score;
- `class_id`: the most recently matched detection class.

The first v1 gate is exact: IDs, ordering, scores, classes, and IEEE-754 box
values must match the NumPy-generated golden output bit for bit. A tolerance is
not the default escape hatch. If a supported platform cannot meet exact parity,
the exception must name the field, platform, numerical backend, measured bound,
and proof that no association or lifecycle decision changes.

## First golden scenarios

The initial dataset-free fixture must cover, in one short deterministic stream:

1. tentative creation and confirmation;
2. high-score association;
3. low-score recovery;
4. one-frame tentative deletion;
5. confirmed coasting through `max_age` and deletion on the following miss;
6. class-aware rejection;
7. empty frames;
8. reset and deterministic ID restart;
9. appearance input when `w_app > 0`;
10. an assignment tie whose detection ordering is fixed.

## Test and rollout plan

1. Add the canonical fixture and SHA-256 digest to `visiontrack`; generate its
   expected output only through the public NumPy tracker.
2. Add a Python validator/runner that rejects malformed input and exact-output
   drift without requiring datasets, models, or network access.
3. Copy the identical fixture bytes into `visiontrack-cpp`; add a digest guard so
   either repository fails when its recorded peer digest is stale.
4. Run the fixture through the public C++ binding and compare exact canonical
   observations. Keep the existing MOT17 parity harness as the real-data gate.
5. Add both dataset-free runners to normal CI. Only then mark synchronization v1
   executable and consider the VisionTrack `0.3.0` release scope frozen.

Research behavior is accepted in Python first. A later contract version may add
bounded anonymous identity continuity only after its gallery, abstention,
expiry, eviction, privacy, and memory semantics have passed Python evaluation.
