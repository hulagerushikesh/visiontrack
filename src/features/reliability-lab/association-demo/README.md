# Prepared association lesson — synthetic, no footage

These are the original canonical JSON exports of the `kalman` case in
`scripts/test-association-workflow.mjs`, retained during the `b4a3d1d` delivery
checks on 2026-11-01. They are produced by source-checkout tooling added after
the published 0.4.0 package. The declared producer version remains 0.4.0;
this does not make `lab-association` part of that published wheel. Original
executing-source fingerprints and Python/NumPy metadata are preserved.

The fixture is two frames, with one detection per frame, original key 7,
score 0.9 and class 1. Boxes are `(10,10,30,30)` then `(11,10,31,30)`.
The sole override is `kf_noise_scale=0.001`; all other settings use the
existing defaults. A synthetic reference box `(10,10,30,30)` in both frames
allows the normal report builder to run; this is not traffic accuracy evidence.

At frame 1, ID 1 was tentative before association. The pair is offered only to
the tentative/high-score stage. Its IoU is 0.9047619047619048 (minimum 0.3),
class is compatible, but squared Mahalanobis distance is 132231.4049586777
(maximum 9.4877). Only that hard gate fails. ID 1 is deleted unconfirmed and
detection 7 starts tentative ID 2. There are no public output boxes. The example
does not establish physical identity or support disabling the gate.

The reader checks all three records with the ordinary strict report, initiation
and association readers, then pins their identifiers. It publishes the complete
triple or nothing. `npm run test:association-demo` checks these exact file bytes,
their lesson facts, invalid/mismatched inputs and cancellation through every
hash stage. `npm run test:association-workflow` generates fresh Python exports
and compares this fixture's configuration, detections, stages, output digest and
timeline with production replay. Do not regenerate the assets just to refresh
producer metadata; choose a new explicitly reviewed lesson if the behavior changes.

| File | SHA-256 of original UTF-8 file including final newline |
| --- | --- |
| `report.json` | `3830be7a5876915a7756b7dcc6d5b1262861f81cba906e0179be57e073ca3692` |
| `initiation-trace.json` | `1cc88cfc764176ca9591d9ee6ba885746e3f0d4988e753a89aed01d8d3cc793c` |
| `association.json` | `0d184dd7981b53bce09d05471f3f33752fc4a6385a6517a151f6c6055ad2e00a` |

The original receipt is retained outside Git at
`visiontrack-walkthrough/association-lab-20261101/vectors.json` in the project
workspace; it is not needed for a fresh checkout or CI. The browser assets above
are self-contained and contain no personal files, paths, footage or credentials.
