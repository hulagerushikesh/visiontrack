/* VisionTrack — mountable, entirely client-side live demo runtime. */
(function () {
  "use strict";

  var modelPromise = null;
  var CLASSES = { person: 1, bicycle: 1, car: 1, motorcycle: 1, bus: 1, truck: 1 };

  function getModel() {
    if (!modelPromise) {
      modelPromise = window.cocoSsd.load({ base: "lite_mobilenet_v2" }).catch(function (error) {
        modelPromise = null;
        throw error;
      });
    }
    return modelPromise;
  }

  function mount(root) {
    var $ = function (id) { return root.querySelector("#" + id); };
    var video = $("src-video"), canvas = $("live-cv");
    var startBtn = $("start-btn"), srcSeg = $("src-seg"), detToggle = $("det-toggle");
    var statusEl = $("status");
    var fpsEl = $("m-fps"), trkEl = $("m-tracks"), idEl = $("m-ids"), detEl = $("m-dets");
    var required = [video, canvas, startBtn, srcSeg, detToggle, statusEl, fpsEl, trkEl, idEl, detEl];
    if (!window.VT || !window.VT.ByteTracker || required.some(function (node) { return !node; })) {
      throw new Error("The live tracker page is missing its required runtime contract.");
    }
    var ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("This browser cannot create the tracker canvas.");

    var tracker = new window.VT.ByteTracker({ nInit: 3, maxAge: 30, trackThresh: 0.5, detThresh: 0.2 });
    var model = null;
    var running = false, source = "webcam", stream = null;
    var showDet = detToggle.checked, fps = 0, lastT = 0;
    var destroyed = false, animationFrame = 0;
    var pendingPlaying = null, pendingCanPlay = null;

    function setStatus(message, tone) {
      if (destroyed) return;
      statusEl.textContent = message;
      statusEl.dataset.tone = tone || "";
    }

    function setRunning(next) {
      running = next;
      startBtn.textContent = next ? "Stop tracking" : "Start tracking";
      startBtn.classList.toggle("on", next);
      startBtn.dataset.running = String(next);
    }

    function clearPlaybackListeners() {
      if (pendingPlaying) video.removeEventListener("playing", pendingPlaying);
      if (pendingCanPlay) video.removeEventListener("canplay", pendingCanPlay);
      pendingPlaying = null;
      pendingCanPlay = null;
    }

    function stopStream() {
      clearPlaybackListeners();
      if (stream) {
        stream.getTracks().forEach(function (track) { track.stop(); });
        stream = null;
      }
      try { video.pause(); } catch (error) { /* media may not have started */ }
      video.srcObject = null;
    }

    function playSoon(successMessage) {
      clearPlaybackListeners();
      pendingPlaying = function () {
        clearPlaybackListeners();
        if (destroyed || !running) return;
        tracker.reset();
        setStatus(successMessage, "ok");
      };
      video.addEventListener("playing", pendingPlaying);
      video.play().catch(function (error) {
        if (destroyed || !running || !error || error.name !== "AbortError") return;
        pendingCanPlay = function () {
          if (pendingCanPlay) video.removeEventListener("canplay", pendingCanPlay);
          pendingCanPlay = null;
          if (!destroyed && running) video.play().catch(function () {});
        };
        video.addEventListener("canplay", pendingCanPlay, { once: true });
      });
    }

    function startWebcam() {
      stopStream();
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setStatus("This browser has no camera API — using the sample clip.", "err");
        selectSource("sample");
        return;
      }
      setStatus("Requesting camera permission…", "wait");
      navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: 960 }, audio: false })
        .then(function (nextStream) {
          if (destroyed || !running || source !== "webcam") {
            nextStream.getTracks().forEach(function (track) { track.stop(); });
            return;
          }
          stream = nextStream;
          video.removeAttribute("src");
          video.srcObject = nextStream;
          playSoon("Tracking your camera — live and on-device.");
        })
        .catch(function () {
          if (destroyed || !running) return;
          setStatus("Camera blocked or unavailable — using the sample clip.", "err");
          selectSource("sample");
        });
    }

    function startSample() {
      stopStream();
      video.loop = true;
      video.muted = true;
      video.playsInline = true;
      video.src = "/assets/street_tracking.mp4";
      playSoon("Tracking the sample street clip — no camera permission needed.");
    }

    function activateSource() { (source === "webcam" ? startWebcam : startSample)(); }

    function selectSource(next) {
      source = next;
      Array.prototype.forEach.call(srcSeg.querySelectorAll("button[data-src]"), function (button) {
        button.setAttribute("aria-pressed", String(button.dataset.src === next));
      });
      if (running) activateSource();
    }

    function detectionsFrom(predictions) {
      var output = [];
      for (var i = 0; i < predictions.length; i++) {
        var prediction = predictions[i];
        if (!CLASSES[prediction.class]) continue;
        var box = prediction.bbox;
        output.push({ box: [box[0], box[1], box[0] + box[2], box[1] + box[3]], score: prediction.score, cls: prediction.class });
      }
      return output;
    }

    function draw(detections, tracks) {
      var width = canvas.width, height = canvas.height;
      ctx.drawImage(video, 0, 0, width, height);
      var scale = Math.max(width, height) / 900;
      var lineWidth = Math.max(2, 2.4 * scale), font = Math.round(15 * scale);
      if (showDet) {
        ctx.setLineDash([6 * scale, 5 * scale]);
        ctx.lineWidth = 1.4 * scale;
        ctx.strokeStyle = "rgba(255,255,255,.45)";
        for (var d = 0; d < detections.length; d++) {
          var detectionBox = detections[d].box;
          ctx.strokeRect(detectionBox[0], detectionBox[1], detectionBox[2] - detectionBox[0], detectionBox[3] - detectionBox[1]);
        }
        ctx.setLineDash([]);
      }
      ctx.font = "600 " + font + "px ui-monospace, Menlo, monospace";
      ctx.textBaseline = "middle";
      for (var i = 0; i < tracks.length; i++) {
        var track = tracks[i], trackBox = track.box(), trail = track.trail;
        ctx.strokeStyle = track.color;
        ctx.lineWidth = lineWidth;
        for (var j = 1; j < trail.length; j++) {
          ctx.globalAlpha = (j / trail.length) * 0.6;
          ctx.beginPath();
          ctx.moveTo(trail[j - 1][0], trail[j - 1][1]);
          ctx.lineTo(trail[j][0], trail[j][1]);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
        ctx.strokeRect(trackBox[0], trackBox[1], trackBox[2] - trackBox[0], trackBox[3] - trackBox[1]);
        var label = "#" + track.id + " " + track.cls;
        var textWidth = ctx.measureText(label).width + 12 * scale, chipHeight = font + 10 * scale;
        ctx.fillStyle = track.color;
        ctx.fillRect(trackBox[0], trackBox[1] - chipHeight, textWidth, chipHeight);
        ctx.fillStyle = "#05070b";
        ctx.fillText(label, trackBox[0] + 6 * scale, trackBox[1] - chipHeight / 2);
      }
      ctx.globalAlpha = 1;
    }

    function loop() {
      if (destroyed || !running) return;
      if (video.readyState < 2) {
        animationFrame = requestAnimationFrame(loop);
        return;
      }
      var width = video.videoWidth, height = video.videoHeight;
      if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
      model.detect(video, 25, 0.2).then(function (predictions) {
        if (destroyed || !running) return;
        var detections = detectionsFrom(predictions), tracks = tracker.update(detections);
        draw(detections, tracks);
        var now = performance.now();
        if (lastT) {
          var instant = 1000 / (now - lastT);
          fps = fps ? fps * 0.85 + instant * 0.15 : instant;
        }
        lastT = now;
        fpsEl.textContent = fps.toFixed(0);
        trkEl.textContent = String(tracks.length);
        idEl.textContent = String(tracker.totalIds);
        detEl.textContent = String(detections.length);
        animationFrame = requestAnimationFrame(loop);
      }).catch(function (error) {
        if (destroyed) return;
        setStatus("Detector error: " + error.message, "err");
        setRunning(false);
        stopStream();
      });
    }

    function onStart() {
      if (!model) return;
      setRunning(!running);
      if (running) {
        activateSource();
        animationFrame = requestAnimationFrame(loop);
      } else {
        if (animationFrame) cancelAnimationFrame(animationFrame);
        animationFrame = 0;
        stopStream();
        setStatus("Stopped. Session IDs remain visible until you start again.", "");
      }
    }

    function onSource(event) {
      var button = event.target.closest("button[data-src]");
      if (button) selectSource(button.dataset.src);
    }
    function onDetectionToggle() { showDet = detToggle.checked; }

    function maybeAutostart() {
      var query = new URLSearchParams(location.search);
      if (!query.has("demo") && query.get("src") !== "sample") return;
      selectSource("sample");
      setRunning(true);
      activateSource();
      animationFrame = requestAnimationFrame(loop);
    }

    startBtn.disabled = true;
    setRunning(false);
    startBtn.addEventListener("click", onStart);
    srcSeg.addEventListener("click", onSource);
    detToggle.addEventListener("change", onDetectionToggle);
    setStatus("Loading detector (COCO-SSD, about 5 MB)…", "wait");
    getModel().then(function (loadedModel) {
      if (destroyed) return;
      model = loadedModel;
      startBtn.disabled = false;
      setStatus("Detector ready — choose a source and press Start tracking.", "ok");
      maybeAutostart();
    }).catch(function (error) {
      setStatus("Detector failed to load: " + error.message, "err");
    });

    return function cleanup() {
      if (destroyed) return;
      destroyed = true;
      running = false;
      if (animationFrame) cancelAnimationFrame(animationFrame);
      animationFrame = 0;
      stopStream();
      video.removeAttribute("src");
      try { video.load(); } catch (error) { /* element may already be detached */ }
      startBtn.removeEventListener("click", onStart);
      srcSeg.removeEventListener("click", onSource);
      detToggle.removeEventListener("change", onDetectionToggle);
      tracker.reset();
    };
  }

  window.VTLive = { mount: mount };

  function mountStandalone() {
    if (document.body && document.body.hasAttribute("data-live-standalone")) mount(document);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountStandalone, { once: true });
  else mountStandalone();
})();
