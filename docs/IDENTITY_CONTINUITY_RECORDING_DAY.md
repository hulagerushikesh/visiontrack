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
