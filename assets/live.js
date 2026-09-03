/* VisionTrack — live in-browser demo glue.
 *
 * Runs the whole tracking pipeline client-side, no server, no video in git:
 *   webcam (or the committed sample clip) -> COCO-SSD detector (TensorFlow.js,
 *   the ONE learned piece) -> the from-scratch JS tracker in tracker.js
 *   (Kalman + Hungarian + ByteTrack) -> boxes + stable ids drawn on a canvas.
 *
 * The detector is deliberately the only imported model: the association, gating,
 * and lifecycle — the actual subject of this project — are all our own code.
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var video = $("src-video"), canvas = $("live-cv"), ctx = canvas.getContext("2d");
  var startBtn = $("start-btn"), srcSeg = $("src-seg"), detToggle = $("det-toggle");
  var statusEl = $("status");
  var fpsEl = $("m-fps"), trkEl = $("m-tracks"), idEl = $("m-ids"), detEl = $("m-dets");

  // COCO classes worth tracking on a street / in a room.
  var CLASSES = { person: 1, bicycle: 1, car: 1, motorcycle: 1, bus: 1, truck: 1 };

  var tracker = new window.VT.ByteTracker({ nInit: 3, maxAge: 30, trackThresh: 0.5, detThresh: 0.2 });
  var model = null;
  var running = false, source = "webcam", stream = null;
  var showDet = true, fps = 0, lastT = 0;

  function setStatus(msg, tone) {
    statusEl.textContent = msg;
    statusEl.dataset.tone = tone || "";
  }

  // ---- model ----
  function ensureModel() {
    if (model) return Promise.resolve(model);
    setStatus("loading detector (COCO-SSD, ~5 MB)…", "wait");
    return window.cocoSsd.load({ base: "lite_mobilenet_v2" }).then(function (m) {
      model = m;
      setStatus("detector ready — press Start.", "ok");
      startBtn.disabled = false;
      return m;
    }).catch(function (e) {
      setStatus("detector failed to load: " + e.message, "err");
      throw e;
    });
  }

  // ---- sources ----
  function stopStream() {
    // Note: no video.load() here — calling it immediately before a new src + play()
    // races the pending play() and throws AbortError. Clearing the source is enough.
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    try { video.pause(); } catch (e) { /* ignore */ }
    video.srcObject = null;
  }

  // Kick playback, tolerating the "play() interrupted by a new load" race:
  // AbortError just means a newer load superseded us — retry once when ready.
  // The success status is driven by the actual `playing` event, not the promise.
  function playSoon(okMsg) {
    var onPlaying = function () {
      video.removeEventListener("playing", onPlaying);
      tracker.reset(); setStatus(okMsg, "ok");
    };
    video.addEventListener("playing", onPlaying);
    var attempt = function () {
      video.play().catch(function (e) {
        if (e && e.name === "AbortError") {
          video.addEventListener("canplay", function once() {
            video.removeEventListener("canplay", once); video.play().catch(function () {});
          }, { once: true });
        }
      });
    };
    attempt();
  }

  function startWebcam() {
    stopStream();
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("this browser has no camera API — using the sample clip.", "err");
      selectSource("sample"); return;
    }
    setStatus("requesting camera…", "wait");
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: 960 }, audio: false })
      .then(function (s) { stream = s; video.srcObject = s; playSoon("tracking your camera — live."); })
      .catch(function () {
        setStatus("camera blocked or unavailable — falling back to the sample clip.", "err");
        selectSource("sample");
      });
  }

  function startSample() {
    stopStream();
    video.loop = true; video.muted = true; video.playsInline = true;
    video.src = "/assets/street_tracking.mp4";
    playSoon("tracking the sample street clip (public-domain footage).");
  }

  function activateSource() { (source === "webcam" ? startWebcam : startSample)(); }

  function selectSource(next) {
    source = next;
    Array.prototype.forEach.call(srcSeg.querySelectorAll("button"), function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.src === next));
    });
    if (running) activateSource();
  }

  // ---- the loop ----
  function detectionsFrom(preds) {
    var out = [];
    for (var i = 0; i < preds.length; i++) {
      var p = preds[i];
      if (!CLASSES[p.class]) continue;
      var b = p.bbox;  // [x, y, w, h]
      out.push({ box: [b[0], b[1], b[0] + b[2], b[1] + b[3]], score: p.score, cls: p.class });
    }
    return out;
  }

  function loop() {
    if (!running) return;
    if (video.readyState < 2) { requestAnimationFrame(loop); return; }

    var w = video.videoWidth, h = video.videoHeight;
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }

    model.detect(video, 25, 0.2).then(function (preds) {
      var dets = detectionsFrom(preds);
      var tracks = tracker.update(dets);
      draw(dets, tracks);

      var now = performance.now();
      if (lastT) { var inst = 1000 / (now - lastT); fps = fps ? fps * 0.85 + inst * 0.15 : inst; }
      lastT = now;
      fpsEl.textContent = fps.toFixed(0);
      trkEl.textContent = String(tracks.length);
      idEl.textContent = String(tracker.totalIds);
      detEl.textContent = String(dets.length);

      requestAnimationFrame(loop);
    }).catch(function (e) {
      setStatus("detector error: " + e.message, "err");
      running = false; startBtn.textContent = "Start";
    });
  }

  // ---- drawing ----
  function draw(dets, tracks) {
    var w = canvas.width, h = canvas.height;
    ctx.drawImage(video, 0, 0, w, h);

    var scale = Math.max(w, h) / 900;      // stroke/text scale with resolution
    var lw = Math.max(2, 2.4 * scale), font = Math.round(15 * scale);

    // raw detections (dashed, faint) — what the detector proposes each frame
    if (showDet) {
      ctx.setLineDash([6 * scale, 5 * scale]);
      ctx.lineWidth = 1.4 * scale;
      ctx.strokeStyle = "rgba(255,255,255,.45)";
      for (var d = 0; d < dets.length; d++) {
        var db = dets[d].box;
        ctx.strokeRect(db[0], db[1], db[2] - db[0], db[3] - db[1]);
      }
      ctx.setLineDash([]);
    }

    ctx.font = "600 " + font + "px ui-monospace, Menlo, monospace";
    ctx.textBaseline = "middle";
    for (var i = 0; i < tracks.length; i++) {
      var t = tracks[i], b = t.box();
      // Kalman trail
      var tr = t.trail;
      ctx.strokeStyle = t.color; ctx.lineWidth = lw;
      for (var j = 1; j < tr.length; j++) {
        ctx.globalAlpha = (j / tr.length) * 0.6;
        ctx.beginPath(); ctx.moveTo(tr[j - 1][0], tr[j - 1][1]); ctx.lineTo(tr[j][0], tr[j][1]); ctx.stroke();
      }
      ctx.globalAlpha = 1;
      // confirmed track box
      ctx.strokeRect(b[0], b[1], b[2] - b[0], b[3] - b[1]);
      // id chip
      var label = "#" + t.id + " " + t.cls;
      var tw = ctx.measureText(label).width + 12 * scale, ch = (font + 10 * scale);
      ctx.fillStyle = t.color;
      ctx.fillRect(b[0], b[1] - ch, tw, ch);
      ctx.fillStyle = "#05070b";
      ctx.fillText(label, b[0] + 6 * scale, b[1] - ch / 2);
    }
    ctx.globalAlpha = 1;
  }

  // ---- wiring ----
  startBtn.disabled = true;
  startBtn.addEventListener("click", function () {
    if (!model) return;
    running = !running;
    startBtn.textContent = running ? "Stop" : "Start";
    startBtn.classList.toggle("on", running);
    if (running) { activateSource(); requestAnimationFrame(loop); }
    else { stopStream(); setStatus("stopped.", ""); }
  });
  srcSeg.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-src]"); if (b) selectSource(b.dataset.src);
  });
  detToggle.addEventListener("change", function () { showDet = detToggle.checked; });

  // Deep-link a running demo: /live?demo=1 auto-starts on the sample clip once the
  // detector is ready (no camera prompt). Handy for sharing and for embedding.
  function maybeAutostart() {
    var q = new URLSearchParams(location.search);
    if (!q.has("demo") && q.get("src") !== "sample") return;
    selectSource("sample");
    running = true; startBtn.textContent = "Stop"; startBtn.classList.add("on");
    activateSource(); requestAnimationFrame(loop);
  }

  ensureModel().then(maybeAutostart).catch(function () {});
})();
