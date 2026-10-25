// Offline DOM/canvas doubles, not browser screenshots or independent human review.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const html = readFileSync(
  new URL("../experiments/_mot17_visual_review.html", import.meta.url),
  "utf8",
);
assert.ok(html.includes("connect-src 'none'"));
assert.ok(!html.includes("<script src="));
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
const data = {
  frames: [36, 37].map((source_frame) => ({
    source_frame,
    image: `../frames/${source_frame}.jpg`,
    references: [
      { id: 85, box: [410, 66, 461, 231] },
      { id: 89, box: [387, 88, 436, 242] },
    ],
    public_tracks: [{ id: 19, box: [400, 75, 451, 239] }],
    detections: [{ row: 1, box: [400, 75, 451, 239], score: 0.9 }],
  })),
  source_window: [36, 57],
  detail_viewport: [307, 6, 575, 337],
  baseline_manifest_sha256: "b".repeat(64),
  rescore_manifest_sha256: "r".repeat(64),
  image_manifest_sha256: "i".repeat(64),
};
const elements = new Map(),
  images = [],
  boxes = [],
  downloads = [],
  urls = [],
  revoked = [];
const context = {
  clearRect() {},
  drawImage() {},
  save() {},
  translate() {},
  restore() {},
  setLineDash() {},
  strokeRect(...box) {
    boxes.push(box);
  },
  fillText() {},
};
function element(id) {
  if (!elements.has(id))
    elements.set(id, {
      value: "",
      textContent: "",
      checked: false,
      disabled: false,
      attributes: {},
      children: [],
      setAttribute(k, v) {
        this.attributes[k] = v;
      },
      append(child) {
        this.children.push(child);
      },
      getContext() {
        return context;
      },
      click() {
        downloads.push(this);
      },
      width: 1920,
      height: 1080,
    });
  return elements.get(id);
}
element("review-data").textContent = JSON.stringify(data);
const sandbox = {
  document: {
    getElementById: element,
    createElement: (tag) => {
      assert.ok(["option", "a"].includes(tag));
      return {
        click() {
          downloads.push(this);
        },
      };
    },
  },
  Image: class {
    constructor() {
      this.naturalWidth = 1920;
      this.naturalHeight = 1080;
      images.push(this);
    }
  },
  Blob,
  URL: {
    createObjectURL(blob) {
      urls.push(blob);
      return "blob:local-notes";
    },
    revokeObjectURL(url) {
      revoked.push(url);
    },
  },
  setTimeout(fn) {
    fn();
  },
  fetch() {
    assert.fail("Review must not fetch or upload anything");
  },
};
runInNewContext(script, sandbox);
assert.equal(images.length, 1);
images.at(-1).onload();
assert.equal(boxes.length, 0, "initial scene pass has no annotations");
assert.match(element("status").textContent, /Source frame 36 · pass 1/);
assert.equal(element("previous").disabled, true);
element("scene-note").value =
  "Two overlapping moving figures; ambiguous initially.";
element("references").onclick();
images.at(-1).onload();
assert.equal(boxes.length, 2);
assert.equal(element("detail").disabled, false);
assert.match(element("legend").textContent, /reference 85/);
element("reference-note").value = "Partial overlap; no label edit justified.";
element("outputs").onclick();
images.at(-1).onload();
assert.equal(
  boxes.length,
  5,
  "third pass adds two references and one saved public track",
);
element("detections").checked = true;
element("detail").checked = true;
element("detail").onchange();
images.at(-1).onload();
assert.equal(boxes.length, 9);
assert.equal(element("scene").width, 268);
assert.equal(element("scene").height, 331);
element("next").onclick();
const stale = images.at(-1);
element("previous").onclick();
const count = boxes.length;
stale.onload();
assert.equal(
  boxes.length,
  count,
  "late old frame cannot draw over the current selection",
);
images.at(-1).naturalWidth = 100;
images.at(-1).onload();
assert.match(element("status").textContent, /Unexpected image dimensions/);
element("next").onclick();
images.at(-1).onerror();
assert.match(element("status").textContent, /Local image unavailable/);
element("raw").onclick();
const beforeRaw = boxes.length;
images.at(-1).onload();
assert.equal(
  boxes.length,
  beforeRaw,
  "raw pass conceals all overlays even with checked controls",
);
assert.equal(element("scene").width, 1920);
element("download").onclick();
assert.equal(urls.length, 0, "empty notes do not create a download");
element("reviewer").value = "offline-fixture";
element("scene-note").value = "Later edited scene description.";
element("output-note").value = "Uncertain; no proposed tracker change.";
element("download").onclick();
const notes = JSON.parse(await urls[0].text());
assert.equal(
  notes.scene_notes_before_first_overlay,
  "Two overlapping moving figures; ambiguous initially.",
);
assert.equal(
  notes.reference_notes_before_first_tracker_overlay,
  "Partial overlap; no label edit justified.",
);
assert.equal(notes.observations.scene, "Later edited scene description.");
assert.equal(notes.independent_review_verified, false);
assert.equal(notes.tracker_or_label_changes, false);
assert.equal(notes.image_manifest_sha256, data.image_manifest_sha256);
assert.equal(downloads.length, 1);
assert.equal(downloads[0].download, "mot17-review-notes.json");
assert.deepEqual(revoked, ["blob:local-notes"]);
console.log(
  "MOT17 staged review offline controls, concealment, stale frames and explicit notes: pass",
);
