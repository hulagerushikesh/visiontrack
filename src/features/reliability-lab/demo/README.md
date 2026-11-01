# Fixed browser teaching example

These are the original numeric JSON bytes from a fresh public-PyPI installation
of `visiontrack-mot[lab]==0.4.0`, prepared on 2026-11-01 with:

```sh
visiontrack lab-demo NEW_OUTPUT_FOLDER --with-initiation --write
```

Only `try-in-browser/report.json` and `initiation-trace.json` are included.
They contain generated objects, not recorded people, media or private datasets.
The report describes 48 synthetic frames, four reference objects, 114 reference
object-frame observations and 64 failure records. Both configurations tie:
FN 23, FP 0, IDSW 0, fragmentation 9 and IDF1 about 0.8878. No winner is selected.

| File | SHA-256 of original bytes |
| --- | --- |
| `report.json` | `8d4551ee789687bdab3126b5ac6e1e9ee2df7545a234006467cc7869548c007a` |
| `initiation-trace.json` | `b7c2317fa61cd912ca5ca1b1ffa4796f24b2e2fb1e69691e5a07c51965881393` |

Report ID: `512a7a79db0535b4c26321def12cb8be514581d7a9f48c73206c5ebb147f2d17`.
Trace ID: `630449be5bc03e231d4bd666ba662c68ba2235dd138854dc619d482e63636a0a`.
The trace includes the producer's Python/NumPy/source identities; rebuilding in
another environment may change its fingerprint. Preserve this example rather
than relabelling it as a future release or current-source provenance.

The page dynamically imports these texts only after **Try guided demo** is
selected. It uses the actual bounded report and initiation readers, checks both
fingerprints and exact report/run/configuration binding, then checks these fixed
IDs before publishing the pair. Original Python number tokens are preserved.
Cancellation discards pending loads/checks. No inference or upload is involved;
the website still downloads its ordinary JavaScript and this example chunk.
The illustrative fixture and user-selected local reports remain separate modes.
Research decision drafting is disabled in guided mode.

`npm run test:guided-demo` verifies the retained bytes, rejection/cancellation,
actual frame 0–2 lifecycle and rendered explanations. Existing initiation tests
separately exercise fresh Python-generated artifacts. These checks do not
establish browser interaction quality, practitioner comprehension, real-world
accuracy, physical identity or product demand.
