"""Build a private offline, staged review of the sealed 36--57 event window.

Reads existing evidence only; no tracker, scoring, network or label modification.
No review is completed automatically. A reviewer starts with unlabelled imagery,
then references, then saved outputs, and can download explicitly authored notes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote

from experiments.mot17_case_baseline import sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import ARCHIVE_SHA256, require
from experiments.mot17_coverage_v2 import RESCORE_MANIFEST, read_packet
from experiments.mot17_review_frames import MEMBERS, WINDOW, check_jpeg, preview
from experiments.mot17_trace_v2 import prepare


def image_packet(path, expected_digest):
    contents = read_packet(path, expected_digest)
    names = {Path(member).name for member in MEMBERS}
    require(set(contents) == names | {"method.json", "acquisition.json"},
            "exact fixed-window image inventory required")
    method, receipt = (json.loads(contents[n]) for n in ("method.json", "acquisition.json"))
    require(all(method.get(key) == value for key, value in preview().items()) and
            method.get("labels_sha256") == ARCHIVE_SHA256,
            "fixed source-frame admission required")
    require(receipt["annotation_members_exact"] is True and set(receipt["files"]) == names,
            "source annotation correspondence required")
    for member in MEMBERS:
        name = Path(member).name
        record, raw = receipt["files"][name], contents[name]
        require(record["source_member"] == member and record["bytes"] == len(raw) and
                record["sha256"] == hashlib.sha256(raw).hexdigest(), "image receipt mismatch")
        check_jpeg(raw)
    return contents


def model(contents, rescore):
    _, selected = prepare(contents, rescore)
    require(selected["source_window"] == list(WINDOW), "same fixed v2 window required")
    event = selected["event"]
    require((event["source_frame"], event["gt_id"], event["previous_hyp_id"], event["hyp_id"])
            == (54, 85, 19, 31), "same first chronological event required")
    rows = [json.loads(line) for line in contents["run-1/raw.jsonl"].splitlines()]
    require([r["source_frame"] for r in rows] == list(range(1, 1051)),
            "complete saved source sequence required")
    frames = []
    for row in rows[WINDOW[0] - 1:WINDOW[1]]:
        references = []
        for identity in (85, 89):
            require(row["gt_ids"].count(identity) == 1, "unique target reference required")
            index = row["gt_ids"].index(identity)
            require(row["gt_classes"][index] == 1 and row["gt_consider"][index] == 1,
                    "scoring pedestrian reference required")
            references.append(dict(id=identity, box=row["gt_xyxy"][index],
                                   visibility=row["gt_visibility"][index]))
        public = [dict(id=identity, box=box) for identity, box in
                  zip(row["track_ids"], row["track_xyxy"], strict=True)
                  if identity in (19, 31)]
        detections = [dict(row=index, box=box, score=score) for index, (box, score) in enumerate(
            zip(row["detections_xyxy"], row["detection_scores"], strict=True), start=1)]
        frames.append(dict(source_frame=row["source_frame"], references=references,
                           public_tracks=public, detections=detections))
    # The detail viewport is fixed for all frames and starts only after the raw
    # scene pass. It is a display crop, never a new dataset annotation or image.
    boxes = [r["box"] for frame in frames for r in frame["references"]]
    roi = [max(0, min(b[0] for b in boxes) - 80), max(0, min(b[1] for b in boxes) - 40),
           min(1920, max(b[2] for b in boxes) + 80), min(1080, max(b[3] for b in boxes) + 80)]
    return dict(schema="visiontrack.mot17-visual-review/v1", source_window=list(WINDOW),
                source_size=[1920, 1080], first_event=event, detail_viewport=roi, frames=frames,
                baseline_manifest_sha256=BASELINE_MANIFEST,
                rescore_manifest_sha256=RESCORE_MANIFEST, independent_review_completed=False,
                tracker_or_label_changes=False)


def render(value):
    template = Path(__file__).with_name("_mot17_visual_review.html").read_text()
    # Script data must not be able to close its own element. Raw values are not
    # interpolated into executable statements or HTML attributes.
    payload = json.dumps(value, sort_keys=True, allow_nan=False).replace("<", "\\u003c")
    return template.replace("__REVIEW_DATA__", payload)


def execute(baseline, rescore_path, images, image_digest, output):
    root = Path(__file__).resolve().parents[1]
    require(not output.exists() and not output.is_symlink(), "new output directory required")
    require(output.parent.is_dir() and not output.resolve().is_relative_to(root),
            "existing private output parent outside repository required")
    before = read_bundle(baseline)
    rescore = read_packet(rescore_path, RESCORE_MANIFEST)
    image_bytes = image_packet(images, image_digest)
    value = model(before, rescore)
    value["image_manifest_sha256"] = image_digest
    for frame in value["frames"]:
        name = f'{frame["source_frame"]:06d}.jpg'
        # URL segments are encoded, and files are already verified regular JPEGs.
        # The generated page reads only these relative paths, never scans folders.
        frame["image"] = quote(Path(os.path.relpath(images / name, output)).as_posix(), safe="/.")
        frame["image_sha256"] = hashlib.sha256(image_bytes[name]).hexdigest()
    output.mkdir()
    write_json(output / "review-data.json", value)
    with (output / "index.html").open("x") as stream:
        stream.write(render(value))
    require(read_bundle(baseline) == before and
            read_packet(rescore_path, RESCORE_MANIFEST) == rescore and
            image_packet(images, image_digest) == image_bytes, "review input changed")
    write_json(output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.iterdir()) if p.is_file()})
    print(output / "index.html")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "rescore", "images", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--image-manifest-sha256", required=True)
    args = parser.parse_args()
    execute(args.baseline, args.rescore, args.images, args.image_manifest_sha256, args.output)


if __name__ == "__main__":
    main()
