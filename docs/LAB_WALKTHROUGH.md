# Your first Reliability Lab walkthrough

Allow 5–10 minutes for the beginner steps. A browser is enough; you do not need
to install anything, use GitHub, record footage, or make a research decision. This session
checks how understandable the Lab is. Your observations help us choose the
next improvements, but they do not establish tracking accuracy or validate a
market.

## First understand the task — 3 minutes

The Lab is a workspace for testing trackers, not the webcam tracker itself.
We compare known reference answers with a tracker's output, explore mistakes,
and only later decide whether a change meets agreed research criteria.

- [ ] Open [the Reliability Lab](https://visiontrack.hulage.in/lab).
- [ ] Start with **New here? Start with one simple example.** Select each of
      the three pillar-example steps. The drawings are a teaching example,
      not evidence from the report below.
- [ ] At **Back in view**, compare the expected ID 7 with the example tracker's
      ID 12. This illustrates a tracking-ID change, not recognition of a named person.
- [ ] Tell us whether the example explains what a tracking mistake means.
      If not, stop here and tell us which part is unclear.

## Explore one reported mistake — 3–5 minutes

- [ ] Choose **Explore the report below**. A variant means one tracker version
      or settings choice. A frame means one picture in a sequence.
- [ ] Find **Explore tracking mistakes** and select **Inspect** on one event.
      Read **What this mistake means** before any technical details.
- [ ] If no pictures are attached, do not look for a missing video: the report
      can describe a mismatch without providing pictures that explain its cause.
- [ ] If images are listed, distinguish the report's list from pictures opened
      in this browser: **Listed in the report**, **Checked in this browser**,
      and **Pictures revealed** are separate counts. Importing `report.json`
      does not open image files. Skip the optional file selection if you do not
      have that event's `manifest.json` and its PNG files. File checks confirm
      that selected files match the evidence records, not that a tracker is accurate.
- [ ] Tell us in your own words what you think the event means, or what is
      still confusing. You do not need to understand every metric.

**You can stop here. Human review and decision downloads are not required for
this beginner walkthrough.** Human review is a researcher's reasoned choice
against agreed criteria, not a test of the reader's technical knowledge. If
the evidence is unclear or insufficient, leave the decision section untouched.

## Optional: explore a prepared report

- [ ] Keep a blank note beside it and write down your browser and device.
- [ ] Locate the prepared synthetic `report.json` linked in the chat. If it is
      unavailable on your device, complete the sample-only steps and leave the
      import steps for our next session.

- [ ] Choose **Import report.json** and select the prepared synthetic report.
- [ ] Check whether you can tell that you have moved from the illustrative
      sample to an imported report.
- [ ] Review one failure event. No decision is necessary.

## Optional advanced rehearsal — only with guidance

This tests saving a record, not whether a tracker should be accepted. Do not
interpret the practice rejection below as a research result. Skip this entire
section if the evidence or criteria are unclear.

- [ ] Find **Human review**, then open **For researchers: draft a new local
      decision**.
- [ ] Only for this guided rehearsal, choose **Reject all variants**. Use `owner-reviewer`
      as the author and `Synthetic usability rehearsal; no real-data acceptance
      decision.` as the rationale. Choose **Use current UTC**.
- [ ] Select **Preview exact decision**. Check whether the displayed outcome,
      author, rationale, and time match what you entered.
- [ ] Choose **Confirm and download decision.json**. Keep the filename
      `decision.json`; browsers can add a number when that filename already
      exists, so use an empty download location or rename this new file if needed.
- [ ] Choose **Select decision.json** in Human review and select that download.
      Note whether the verified read-only result is understandable.
- [ ] Choose **Return to sample** at the top. Check that the sample is clearly
      identified again.

Saving into the original bundle with the terminal commands is optional for
this session. We can do that together later. This synthetic report has no
attached image evidence, so the absence of footage or playback images is
expected; report import does not create those files.

## Send your observations — 3 minutes

Copy this short template into the chat or your own private note:

```text
Browser/device:
What I thought the Lab would do:
Last step I completed:
Step where I needed help:
Labels or metrics I did not understand:
What I expected versus what happened:
Most useful part:
One change I would make first:
Overall ease of use (1–5):
```

If a step blocks you, record it and move on. Completing every checkbox is less
valuable than learning where the workflow needs help. A screenshot is optional.

## Later: the real-data milestone

No camera setup or volunteer recruitment is required for this walkthrough.
When you are ready for that separate milestone, we will choose the setting,
agree on the recording and consent arrangements, and freeze the experiment
before collection. The detailed plan is in the
[consented capture plan](IDENTITY_CONTINUITY_CAPTURE_PLAN.md).
