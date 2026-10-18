# Your first Reliability Lab walkthrough

Allow 15–20 minutes. A browser and the prepared synthetic `report.json` are
enough; you do not need to install anything or record footage. This session
checks how understandable the Lab is. Your observations help us choose the
next improvements, but they do not establish tracking accuracy or validate a
market.

## Before you start — 2 minutes

- [ ] Open [the Reliability Lab](https://visiontrack.hulage.in/lab).
- [ ] Keep a blank note beside it and write down your browser and device.
- [ ] Locate the prepared synthetic `report.json` linked in the chat. If it is
      unavailable on your device, complete the sample-only steps and leave the
      import steps for our next session.

## Explore the sample — 5 minutes

- [ ] Before reading the instructions in detail, write one sentence describing
      what you think this page lets you do.
- [ ] Look at the two tracker variants and their measurements. Write down what
      you understand and which labels need an explanation. Understanding every
      metric is not required.
- [ ] Find **Inspect the failure set**, try one filter, and select **Inspect**
      on an event. Describe the event in your own words.
- [ ] Look for an explanation of where files are processed and how a human
      decision is made. Note whether you found it easily.

## Try your own local report — 5–8 minutes

- [ ] Choose **Import report.json** and select the prepared synthetic report.
- [ ] Check whether you can tell that you have moved from the illustrative
      sample to an imported report.
- [ ] Review one failure event, then find **Human review** and **Draft a new
      local decision**.
- [ ] For this rehearsal, choose **Reject all variants**. Use `owner-reviewer`
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
