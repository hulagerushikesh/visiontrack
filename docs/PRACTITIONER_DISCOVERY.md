# VisionTrack practitioner discovery playbook

## Purpose

VisionTrack has a working local-first Reliability Lab, but it does not yet have
evidence that a particular market or workflow needs it. This playbook defines
the next product-discovery step without treating interviews as validation by
default or choosing a vertical before the evidence exists.

The discovery question is:

> Do teams deploying multi-object tracking repeatedly lose time or confidence
> when selecting, diagnosing, or accepting tracker behavior—and will they use a
> local, evidence-producing workflow to make that decision?

The first round targets **5–10 practitioners**. At least three must have direct
experience deploying or evaluating tracking on real footage. The round is
complete only when the notes, evidence rights, and scoring rubric below have
been filled in; a conversation count alone is not completion.

## What this round may and may not decide

It may establish:

- which decision is expensive today;
- which tracking failure is operationally important;
- what evidence teams currently trust;
- whether local-only processing is necessary or merely preferable;
- whether representative clips and/or detections can legally be evaluated;
- whether a team will test the current Reliability Lab on its own problem.

It must not promise:

- named-person or global identity recognition;
- indefinite storage of identities or source video;
- that VisionTrack owns detector quality, deployment infrastructure, or every
  downstream analytics workflow;
- a particular vertical, feature, or accuracy improvement before evidence;
- confidentiality, security, or legal terms that have not been formally agreed.

## Participant mix

Recruit participants across roles and conditions rather than ten people from
one convenient community.

| Dimension | Desired coverage |
|---|---|
| Role | CV/ML engineer, applied researcher, deployment/edge engineer, technical product owner |
| Stage | Prototype, pilot, and production experience |
| Domain | At least three of retail, sports, traffic, warehouse, robotics, security, or another observed domain |
| Scale | Single camera and multi-camera/site experience |
| Outcome | At least three participants responsible for a ship/no-ship or configuration decision |

Exclude people whose only experience is watching a demo or training a detector
without evaluating identity continuity. Their feedback can be useful later but
does not validate the first user defined in `PRODUCT_RESEARCH_STRATEGY.md`.

## Screener

Record concise answers before scheduling a full interview:

1. What is your role, and have you evaluated or deployed multi-object tracking
   on real footage in the last 18 months?
2. What objects, camera setup, and operational outcome were involved?
3. Were you responsible for choosing a tracker/configuration or diagnosing its
   failures?
4. Can you describe a recent failure without disclosing restricted material?
5. Could your organization provide any consented, licensed, synthetic, or
   sanitized clip/detection stream for local evaluation?
6. Are source video, crops, detections, embeddings, or derived reports subject
   to retention, location, or access restrictions?
7. Would you be willing to test a local prototype in a later session?

Do not ask for files during screening. A “yes” to sharing evidence starts a
separate rights and handling check; it is not permission to receive or retain
anything.

## 45-minute interview guide

### 1. Context — 5 minutes

- What system were you building and what decision did tracking support?
- Where did detections come from, and which parts did your team control?
- What made a tracking result acceptable enough to deploy?

### 2. Last concrete failure — 15 minutes

Ask for the most recent real incident, not requested features:

- Walk through the last time tracking behaved badly enough to block, delay, or
  weaken a release.
- What did a person see in the footage or output?
- Was it an ID switch, fragmentation, miss, false positive, re-entry problem,
  counting/dwell error, detector error, or something else?
- How was the cause isolated? Which tools, scripts, screenshots, or meetings
  were needed?
- How long did diagnosis and re-evaluation take, and who participated?
- What configuration or implementation changed? How was the change accepted?
- Did the fix generalize to other cameras or conditions? How did you know?
- What was the cost of a wrong decision—engineering time, delayed launch,
  incorrect analytics, manual review, safety risk, or customer trust?

### 3. Current workflow and evidence — 10 minutes

- How do you compare two configurations using exactly the same evidence?
- Which metrics are trusted, and which hide important failure costs?
- Can a reviewer move from an aggregate metric to the exact frame/track?
- Are runs content-addressed or otherwise reproducible later?
- Is a human acceptance decision recorded with the evidence used to make it?
- What cannot leave the site or machine?
- Which existing tools are indispensable, and where do they stop helping?

Do not demonstrate VisionTrack before this section is complete. Early demos
turn a problem interview into feedback on the solution already shown.

### 4. Concept test — 10 minutes

Give only this neutral description:

> A local tool replays one fixed detection stream through controlled tracker
> variants, reports metrics and failure events, lets a reviewer inspect exact
> evidence, and records the human acceptance decision and runtime lineage.

Then ask:

- Where, if anywhere, would this have changed the incident you described?
- Which input and output would be required for a real trial?
- What would make the report untrustworthy or unusable?
- What would you still need from annotation, detector, deployment, or data
  platforms?
- Would you spend 45–60 minutes testing it on one representative failure? What
  must be true before you can do that?

Record objections verbatim. “Interesting” is not evidence of willingness.

### 5. Close — 5 minutes

- Ask permission for a follow-up prototype test.
- Discuss evidence categories, never request an unapproved transfer.
- Ask for one referral to another practitioner with direct deployment history.
- Confirm how notes may be used and whether attribution is allowed.

## Interview record

Create one private record per participant outside the public repository. Use a
random participant ID rather than a personal name in analysis exports.

```text
participant_id:
date_utc:
interviewer:
role_and_domain:
deployment_stage:
camera_scope:
decision_owned:
last_failure:
failure_category:
operational_consequence:
current_diagnostic_workflow:
time_or_cost_estimate:
trusted_evidence:
privacy_or_retention_constraints:
existing_tools:
concept_reaction:
blocking_objections:
trial_commitment: none | conditional | scheduled
trial_conditions:
evidence_possible: none | metadata | detections | sanitized_media | source_media
follow_up:
quotes_allowed: no | anonymous | attributed
```

Do not commit interview notes, contact details, private URLs, credentials, or
customer evidence to either VisionTrack repository.

## Evidence and rights intake

No clip, frame, crop, detection file, embedding, or annotation enters the Lab
until all applicable fields below are explicitly known.

| Field | Required decision |
|---|---|
| Provider | Organization or authorized individual supplying it |
| Rights basis | Owner-created, licensed, consented, public-license, or synthetic |
| Intended use | Private evaluation, reproducible research, public demo, or publication |
| People/data sensitivity | Whether people, faces, plates, screens, locations, or confidential operations appear |
| Allowed processing location | Provider machine, a named local machine, or another approved boundary |
| Allowed derivatives | Detections, annotations, crops, embeddings, metrics, screenshots, reports |
| Retention | Exact deletion/expiry requirement for source and derivatives |
| Access | Named people or roles allowed to handle it |
| Publication | None, aggregate only, redacted examples, or explicitly approved artifacts |
| Revocation/contact | How permission changes and deletion requests are communicated |

If any required decision is unknown, do not copy the evidence. Prefer, in
order: synthetic reproduction, provider-run evaluation, detections without
pixels, sanitized media, and finally identifiable source media when truly
necessary and authorized.

The current Lab does not upload selected files, does not scan directories, and
does not retain image evidence by default. Those technical properties reduce
risk but do not replace permission or an agreed handling policy.

## Failure-case intake

For every usable case, capture the problem before tuning anything:

```text
case_id:
participant_id:
domain_and_camera_scope:
object_class:
operational_decision:
observed_failure:
expected_behavior:
failure_category:
detector_and_version:
tracker_and_version:
known_configuration:
available_inputs:
available_ground_truth:
conditions: crowding | occlusion | blur | viewpoint | lighting | camera_motion | other
business_or_research_cost:
rights_intake_status:
retention_deadline:
candidate_lab_question:
```

“The ID changed” is not yet a complete case. The intake must distinguish a
continuous-track fragmentation from re-entry after retirement, cross-camera
identity, detector disappearance, and a request for persistent recognition.
These imply different contracts and different risks.

## Scoring rubric

After the interview, score each dimension from 0 to 3 using the evidence in the
record. Do not score enthusiasm.

| Dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Repeated pain | None | One anecdote | Recurred | Recurrent across projects/sites |
| Cost | No consequence | Minor inconvenience | Measurable engineer/manual cost | Release, revenue, safety, or trust impact |
| Reliability Lab fit | Not tracking diagnosis | Adjacent | Comparison/diagnosis helps | Exact workflow matches a current decision |
| Evidence access | Impossible | Description only | Detections/synthetic reproduction | Lawful representative media + GT/labels |
| Trial commitment | Declines | General interest | Conditional named follow-up | Trial scheduled with owner and case |
| Local-first value | Irrelevant | Preference | Material constraint | Required for evaluation/adoption |

Use the score to compare cases, not to create a false universal cutoff. A
high-impact case with no lawful evidence may be commercially interesting but is
not yet a buildable research partnership.

## Synthesis and decision gate

At the end of 5–10 interviews, produce an anonymized synthesis containing:

1. participant mix and limitations;
2. repeated decisions and failure categories;
3. current alternatives and their shortcomings;
4. cost evidence rather than feature votes;
5. privacy, retention, and deployment constraints;
6. evidence availability and representativeness;
7. prototype commitments and conditions;
8. strongest counter-evidence to the Reliability Lab thesis;
9. a recommendation: proceed, narrow/re-interview, or stop/pivot.

The Stage 0 gate passes only when:

- at least three independent teams describe a repeated, expensive
  tracker-selection or failure-diagnosis problem;
- at least three prospective design partners agree to test a local prototype;
- at least one representative case can be evaluated lawfully, even if the data
  must remain on the provider's machine; and
- the desired outcome depends materially on tracking rather than only on a
  better detector, annotation service, dashboard, or infrastructure.

Passing this gate permits a one-page problem statement and one bounded
evidence-producing prototype. It does **not** permit global identity, indefinite
retention, or a full vertical application.

If the gate fails, preserve the negative result. Do not compensate by adding
features. Narrow the user/problem, investigate the adjacent cause revealed by
the interviews, or stop the product path while keeping VisionTrack as a useful
research system.

## Immediate operating checklist

- [x] Create a private interview-notes location with access control and a
      deletion policy; keep it outside both public repositories.
- [x] Build an initial ten-lead candidate-source list spanning tracker/evaluation
      tooling, traffic, sports, fisheries, autonomous racing, annotation, and
      edge deployment; treat every lead as unqualified until screening.
- [x] Review every public lead's appropriate contact route, prioritize a
      five-lead mixed first wave, and prepare restrained unsent outreach drafts
      with an explicit owner-approval gate.
- [x] Personalize four public first-wave drafts against each project's actual
      tracking/evaluation scope; keep every message on hold and leave the fifth
      warm-referral slot visibly blocked rather than inventing a contact.
- [x] Prepare response triage, written screening, consent-aware scheduling,
      interview facilitation, anti-bias prompts, post-call scoring, and an
      outreach audit log without authorizing any external message.
- [ ] Replace three owner-network placeholders with real retail, warehouse, or
      locally accessible deployment decision owners; then approve the balanced
      first wave before sending any message.
- [ ] Screen candidates using the seven questions above.
- [ ] Schedule and conduct 5–10 interviews using the same guide.
- [ ] Complete a score and follow-up decision after every interview.
- [ ] Run rights intake before receiving any evidence.
- [ ] Register each usable failure case before running or tuning VisionTrack.
- [ ] Invite at least three qualified participants to a local prototype test.
- [ ] Produce the anonymized synthesis and apply the Stage 0 gate.
- [ ] Only after the gate passes, write the one-page product problem statement
      and select a vertical from evidence.
