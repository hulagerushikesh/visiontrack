# VisionTrack research-lead path

This path is for the project owner. It answers four questions:

1. What have we actually built?
2. What research are we doing now?
3. What area are we targeting next?
4. What new research thread are we trying to open to the world?

## The short answer

VisionTrack is not trying to become another generic detector or tracker wrapper.
It is building an **open, reproducible tracking reliability lab** and studying
**selective, bounded, anonymous identity continuity**.

The product question is:

> Can a team make a safer tracker/configuration decision from controlled,
> inspectable evidence instead of benchmarks, screenshots, and intuition alone?

The future research question is:

> When a recently disappeared anonymous object returns, can the system restore
> continuity under a fixed false-restoration and memory budget—and explicitly
> refuse when the evidence is unsafe?

## Three connected research areas

### 1. Tracking reliability and diagnosis — current product research

We study why a tracker succeeds or fails under controlled changes. The
Reliability Lab replays the same detection evidence through variants, records
lineage and metrics, extracts failure events, exposes exact evidence, and ties
the final choice to a human decision.

This area is about **causal confidence**: not only which score is higher, but
what changed, where it helped, where it hurt, and whether the result can be
reproduced.

### 2. Selective bounded identity continuity — next scientific research

Normal tracking connects nearby frames. It usually creates a new `track_id`
after a track is retired. Our proposed research separates:

- `track_id`: one continuous visible trajectory;
- `anonymous_identity_id`: tracklets linked only inside an authorized site,
  camera group, session, and retention window.

The key word is **selective**. The system is allowed to abstain and create a new
anonymous identity. It is not forced to match every return to somebody in
memory.

The key word is **bounded**. Candidate identities expire; memory, time, camera
scope, and storage are explicit experimental variables rather than an infinite
gallery assumption.

### 3. Verified acceleration — systems research

VisionTrack C++ asks whether accepted NumPy behavior can become faster without
quietly becoming different. Exact fixtures, reset determinism, trajectory
parity, toolchain evidence, and honest benchmarks form the runtime contract.

The research order is:

```text
understand in NumPy
  -> measure and reject weak ideas
  -> freeze accepted behavior
  -> port to C++
  -> prove parity
  -> measure deployment value
```

## What is already known versus still unknown

| Status | Question |
|---|---|
| Built | Can we inspect and test the tracker from geometry through lifecycle? |
| Built | Can one fixed detection stream drive controlled, immutable comparisons? |
| Built | Can reports, evidence, playback, and human decisions preserve lineage locally? |
| Built | Can the C++ sibling reproduce the frozen tracker contract and expose honest performance evidence? |
| Being validated | Do real deployment teams repeatedly pay for tracker selection and failure diagnosis? |
| Unknown | Which vertical has the strongest painful decision and lawful representative evidence? |
| Future research | At a fixed false-restoration budget, when should a retired anonymous identity be restored? |
| Future research | How do gallery size, retention, crop quality, memory policy, context, and domain shift change safety? |

Do not confuse a built mechanism with a validated product, or a proposed
hypothesis with a research result.

## The research thread we want to open

The contribution is not “recognize everyone forever.” Existing systems often
optimize association accuracy, add ReID, or scale a vector database. VisionTrack
will instead make the **right to refuse an identity match** a first-class output
and measure that refusal against bounded memory and operational cost.

The thread has five parts:

1. **Evidence before selection.** Tracker choices carry exact reproducible
   failure evidence, not just a leaderboard number.
2. **Anonymous continuity, not named recognition.** The useful product event may
   be a visit, trajectory, dwell, or zone transition without knowing a name.
3. **Abstention as correctness.** Creating a new anonymous identity can be safer
   than a confident-looking false restoration.
4. **Memory as an experimental budget.** Accuracy is reported against bytes,
   latency, retention, gallery size, and expiry—not with unlimited history.
5. **Reference-to-runtime proof.** Behavior earns acceleration only after its
   assumptions and decisions are frozen and parity-tested.

A successful publication or open benchmark would make false restoration,
coverage/risk, expiry, and memory cost visible together. A useful negative
result—showing where continuity is unsafe—is still a contribution.

## Research questions to master

- **RQ5 — Selective ReID:** when should the system restore or abstain at a fixed
  false-restoration budget?
- **RQ6 — Gallery scale:** what breaks as candidates, retention, prototypes,
  and quantization change?
- **RQ7 — Crop quality:** can quality-gating a smaller model beat blindly using
  a larger one?
- **RQ8 — Memory policy:** which bounded prototype policy preserves the most
  identity evidence per byte and millisecond?
- **RQ9 — Context:** how much do time, zones, camera topology, size, and
  direction reduce unsafe matches?
- **RQ10 — Confidence transfer:** how can the system detect when thresholds no
  longer transfer to a new detector, camera, or gallery size?

These questions are future work until hypotheses, thresholds, data rights, and
evaluation protocols are registered.

## Your six-week mastery plan

### Week 1 — Explain the complete system

- Complete Levels 0–3 of [`ZERO_TO_HERO.md`](ZERO_TO_HERO.md).
- Draw the detector/tracker/evaluator/Lab/runtime chain from memory.
- Explain why `track_id != person identity`.

Deliverable: a five-minute explanation for a non-technical listener.

### Week 2 — Read one tracking decision end to end

- Trace geometry, Kalman state, assignment, ByteTrack stages, and lifecycle.
- Complete the four dataset-free exercises.
- Inspect one failure event and identify competing causes.

Deliverable: one annotated frame sequence and cause tree.

### Week 3 — Learn evaluation and research discipline

- Compare HOTA, IDF1, MOTA, failure events, and an operational metric.
- Read one project experiment report and list its controls and limitations.
- Write what result would falsify the preferred explanation.

Deliverable: a one-page experiment critique.

### Week 4 — Operate the Reliability Lab

- Produce the synthetic bundle.
- Trace fingerprints from input through report and decision.
- Explain why the Lab does not automatically declare a winner.

Deliverable: a reproducible acceptance memo using only sealed evidence.

### Week 5 — Master the research frontier

- Study RQ5–RQ10 and the bounded storage model.
- Design one synthetic re-entry experiment without implementing it.
- Specify population, absence, ambiguity, memory, abstention, and failure budget.

Deliverable: a pre-registration draft with a negative-result condition.

### Week 6 — Master the two-repository contract

- Complete the NumPy/C++ parity capstone.
- Explain why faster-but-different is a failed port.
- Decide which proposed behaviors stay in Python and what evidence would allow
  them to cross into C++.

Deliverable: a ten-minute project/research presentation with boundaries and
next gates.

## Questions you should be able to answer at any time

1. What user decision are we improving?
2. Is the current claim product evidence, scientific evidence, or engineering
   evidence?
3. Which input is held fixed?
4. Which variable changes?
5. What failure budget is declared before seeing the result?
6. What observation would make us stop or narrow the work?
7. Is any identity named, global, cross-purpose, or retained indefinitely?
8. Does the result depend on detector quality rather than tracking?
9. Can another machine reproduce the decision?
10. Has the behavior earned a C++ port, or is it still experimental?

## Boundaries that protect the direction

VisionTrack does not currently claim:

- persistent recognition of the world's population;
- reliable identity after arbitrary time or camera changes;
- ownership of detector quality;
- that one benchmark winner is best for every deployment;
- that a technical demo proves a market;
- that public availability grants rights to retain or identify people.

The strongest direction is narrower and more defensible: explain tracking
behavior, preserve the evidence behind a decision, study bounded anonymous
continuity, refuse unsafe matches, and accelerate only verified behavior.

## Definition of mastery

You have mastered the project when you can explain its scope to a beginner,
challenge its preferred hypothesis like a reviewer, operate its evidence
workflow like an engineer, protect its data boundary like a product owner, and
say “not yet” when a feature has not earned its claim.
