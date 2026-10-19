# Your recording-day checklist

For the project owner, prepared 2026-10-19. **Setup guide, not approval to
record.** You do not need to understand JSON, run a tracking model, or decide
which algorithm is better tomorrow. The goal is a small, reviewable research
recording, not a public demo or a database of people.

## First, tell me these four things

1. How many adults, including you if participating, voluntarily want to help?
2. What private indoor location can you use with the required permission and
   without incidental bystanders?
3. Will you use a laptop webcam or a phone on a fixed stand?
4. Who can help you independently review the footage afterward?

Do not send names, contact details, consent forms, or footage in chat. A count
and general description are enough. We will use these answers to finalize the
plan **before** recording. If only one or two people are available, we can do
a pipeline rehearsal; do not claim an unseen-person evaluation. The proposed
held-out-person pilot needs at least two separate pairs for development and
test, with no person appearing in both. Four volunteers is a practical minimum
for those paired scenarios, not a statistically sufficient study.

## Current setup choice — rehearsal first

When only two willing adults are available, start with a pipeline rehearsal,
not a participant-disjoint development/test study. Availability is **not
consent or a completed setup check**. Do not assign the same two people to both
splits to make a manifest pass. Actual participant, location and permission
records belong in the private study workspace, not this public guide.

Prefer the laptop webcam for the first rehearsal because it is easier to
operate and inspect locally. Use a fixed phone stand instead if the webcam
cannot show full bodies and a clear exit. A living-room corner facing an open
walking area and doorway can work; another location is not required if the
venue permissions, background and bystander checks pass. Turning away from
the lens is not a scene exit. Aim for landscape 720p/30 fps **if supported**;
verify actual output rather than assuming the selected setting was applied.

Before filming anyone, make a short empty-room test clip using your local
recording app. The website's live tracker is not the research recorder. Save
the clip outside both repos and outside cloud-synced folders. I can help with
the optional technical check below; you do not need to operate it unaided.

### Optional local recording check

From the local VisionTrack checkout, with FFmpeg's `ffprobe` installed:

```bash
python -m experiments.reentry_recording_check --video /private/path/empty-room-test.mp4
```

This reads one explicitly selected local MP4/MOV/MKV/WebM/AVI, at most 2 GiB.
It does not open a camera, upload or display media, change the file, export
pictures, or run detection/identity models. It uses local-file-only probing,
restricted container formats, a 20-second deadline and a 64 KiB stdout cap.
Use a maintained local FFmpeg installation and trusted owner-recorded files;
these restrictions are not a sandbox for arbitrary hostile media.

The output contains resolution, reported nominal/average frame rates, reported
duration and audio-stream count, with warnings for missing/differing rates or
audio. It omits filenames, location tags and other free-text media metadata.
`30` means 30 fps; `30000/1001` is about 29.97 fps and is not silently rounded.
An audio stream can contain silence: its presence is a settings warning, not
proof of a recorded conversation. Return code 0 means the metadata was read,
**not that warnings are absent or the recording is approved**. Code 2 means
the check failed; check the local file/container, FFmpeg and optional manifest.

For an already frozen full-study plan only, add
`--manifest /private/path/pilot-plan.json` to compare reported resolution and
both reported rates exactly. Do not use the example manifest as your actual
plan. A mismatch is a warning; the tool never modifies a frozen plan or media.
Keep populated results private. Dimensions describe the encoded video; phone
rotation/display orientation still needs visual checking. Even matching rates
do **not** verify constant frame timing, dropped frames, completeness, scene
exits, consent or accuracy.
Before frame-to-seconds research scoring, validate actual timestamps separately.
For a two-person rehearsal, omit the manifest rather than inventing a test split.

## Before turning on recording

- [ ] Explain to each adult: this studies temporary anonymous tracking when
      someone leaves and returns, not names or face recognition. Describe what
      video and derived data will be retained, who can access it, the specific
      research use, retention/deletion dates, and how to withdraw. Obtain the
      appropriate informed consent and venue/recording permissions. Declining
      must be fine. Availability or friendship is not consent.
- [ ] Keep consent/contact records separate from randomly coded study records.
      Keep raw footage and any derived person features outside both repos,
      locally with restricted access and encryption. Check camera/cloud-sync
      settings; do not post footage or upload it to the website or chat.
- [ ] Use one stationary camera with a clearly visible scene boundary. Avoid
      mirrors, screens showing other people, private papers, and bystanders.
      No audio is needed; disable it where possible. Pause if a nonparticipant
      enters and exclude the affected take.
- [ ] Choose the actual frame rate/resolution, absence intervals, gallery
      capacity/TTL, scenario counts and permitted scene changes with me. A
      phone recording should have stable timing; we will check it before use.
- [ ] Save those choices in the private capture manifest and record its
      fingerprint in a dated private freeze log before the first take. I can
      help run the existing preflight. A valid file does not prove consent.

If any item is unclear, use the session for camera/setup practice only and
do not record people for the study yet.

## The seven situations we want to observe

Use different participants and recordings for development and test. Plan the
counts in advance; keep test footage unopened by the person tuning the system.
Within each authorized session, record a continuous view so an exit and return
can actually be verified; do not pause the camera to manufacture a gap.

| Situation | What volunteers do | Why it matters |
|---|---|---|
| New arrival | Someone enters who has not previously appeared in this session | Must not inherit another person's label |
| Short return | Someone fully exits the visible scene, waits the agreed short interval, and returns | Tests recovery while memory should remain available |
| Longer return | Repeat with the agreed longer interval, still before memory expiry | Tests a harder eligible return |
| Expired return | Return after the agreed memory lifetime | Must not be counted as an eligible recovery |
| Similar clothing | A genuinely new participant enters wearing similar everyday clothing | Tests mistaken matches, without requiring identical outfits |
| Hidden but still present | A participant is briefly hidden behind an object/person without leaving the scene | Distinguishes occlusion from an exit |
| New session | End the session and start a separately labeled recording | Tests that no identity is carried across the reset |

Do not pick arbitrary timings from this table; finalize and freeze the actual
numbers first. Keep ordinary activity between scripted events. Record missing,
failed, bystander-affected, or withdrawn takes honestly; never quietly replace
them after seeing model results.

## After recording

1. Save the original files locally under random recording/session codes. Keep
   a private participant-group mapping so we can detect split leakage; names
   do not belong in the event ledger or Git.
2. Two reviewers separately mark who entered, whether they really exited, and
   the relevant frames **before seeing tracker decisions**. You are labeling
   what happened in the video, not approving a model. Record disagreements;
   unresolved events remain excluded/indeterminate.
3. Reconcile every planned take with the existing recorded/missing/excluded
   inventory and reviewed ledger, then run the metadata preflight. A successful
   check still requires human rights, footage and truth review.
4. Keep new private recordings separate from the
   [existing-dataset intake](IDENTITY_CONTINUITY_DATASET_INTAKE.md). We will
   evaluate only after source admission and the frozen comparison plan.

For the full research constraints and existing commands, see the
[capture plan](IDENTITY_CONTINUITY_CAPTURE_PLAN.md). No fixed success percentage
is promised: a small pilot can reveal problems but cannot establish the
registered 1% false-restoration risk bound.
