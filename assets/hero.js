/* VisionTrack — ambient hero: a live tracking scene rendered from scratch.
   Self-contained (no data dependency): objects drift, each holding a stable
   track id through crossings, with fading Kalman trails and periodic
   detection→association pulses. The subject itself, moving. Reduced-motion
   draws a single static frame; no-JS falls back to the poster gif. */
(function () {
  var canvas = document.getElementById("hero-cv");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");

  var W = 1280, H = 720, M = 90;            // scene units + margin
  var TRACK = ["#22d3ee", "#34d399", "#fbbf24", "#f472b6", "#a78bfa", "#60a5fa"];
  var DET_PERIOD = 66, DET_HOLD = 12;       // frames between / duration of detection pulses

  // deterministic RNG so the scene always looks composed, never random-ugly
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var rnd = mulberry32(7);

  var objs = [];
  for (var i = 0; i < 6; i++) {
    var w = 78 + rnd() * 46, h = w * (1.5 + rnd() * 0.5);
    objs.push({
      id: 1 + i, color: TRACK[i % TRACK.length],
      x: M + rnd() * (W - 2 * M), y: M + rnd() * (H - 2 * M),
      vx: (rnd() - 0.5) * 3.0, vy: (rnd() - 0.5) * 2.2,
      w: w, h: h, ph: rnd() * 6.28, trail: []
    });
  }

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var frame = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);

  function fit() {
    var r = canvas.getBoundingClientRect();
    if (!r.width) return;
    canvas.width = Math.round(r.width * dpr);
    canvas.height = Math.round(r.width * dpr * H / W);
  }
  fit();
  if (window.ResizeObserver) new ResizeObserver(fit).observe(canvas);
  else window.addEventListener("resize", fit);

  function step() {
    for (var k = 0; k < objs.length; k++) {
      var o = objs[k];
      o.ph += 0.012;
      o.x += o.vx + Math.cos(o.ph) * 0.5;
      o.y += o.vy + Math.sin(o.ph * 0.7) * 0.4;
      if (o.x < M) { o.x = M; o.vx = Math.abs(o.vx); }
      if (o.x > W - M) { o.x = W - M; o.vx = -Math.abs(o.vx); }
      if (o.y < M) { o.y = M; o.vy = Math.abs(o.vy); }
      if (o.y > H - M) { o.y = H - M; o.vy = -Math.abs(o.vy); }
      o.trail.push([o.x, o.y]);
      if (o.trail.length > 36) o.trail.shift();
    }
    frame++;
  }

  function draw() {
    var s = canvas.width / W;                // device px per scene unit
    ctx.setTransform(s, 0, 0, s, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#04060a";
    ctx.fillRect(0, 0, W, H);

    // faint reference grid
    ctx.strokeStyle = "rgba(255,255,255,.045)";
    ctx.lineWidth = 1 / s;
    for (var gx = 0; gx <= W; gx += 80) { ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, H); ctx.stroke(); }
    for (var gy = 0; gy <= H; gy += 80) { ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke(); }

    var detOn = (frame % DET_PERIOD) < DET_HOLD;
    var detA = detOn ? 1 - (frame % DET_PERIOD) / DET_HOLD : 0;

    for (var k = 0; k < objs.length; k++) {
      var o = objs[k], t = o.trail;
      // Kalman-history trail, fading
      for (var j = 1; j < t.length; j++) {
        ctx.strokeStyle = o.color;
        ctx.globalAlpha = (j / t.length) * 0.5;
        ctx.lineWidth = 2 / s;
        ctx.beginPath(); ctx.moveTo(t[j - 1][0], t[j - 1][1]); ctx.lineTo(t[j][0], t[j][1]); ctx.stroke();
      }
      ctx.globalAlpha = 1;

      var bx = o.x - o.w / 2, by = o.y - o.h / 2;

      // raw detection (dashed white) snapping to the object, then associating
      if (detOn) {
        ctx.setLineDash([7 / s, 6 / s]);
        ctx.strokeStyle = "rgba(255,255,255," + (0.28 + 0.4 * detA).toFixed(3) + ")";
        ctx.lineWidth = 1.5 / s;
        var jit = 9 * detA;
        ctx.strokeRect(bx + jit, by - jit, o.w, o.h);
        ctx.setLineDash([]);
      }

      // confirmed track box
      ctx.strokeStyle = o.color;
      ctx.lineWidth = 2.6 / s;
      ctx.strokeRect(bx, by, o.w, o.h);

      // id chip
      ctx.font = "600 22px ui-monospace, Menlo, monospace";
      var label = "#" + o.id, tw = ctx.measureText(label).width + 14;
      ctx.fillStyle = o.color;
      ctx.fillRect(bx, by - 26, tw, 24);
      ctx.fillStyle = "#04060a";
      ctx.textBaseline = "middle";
      ctx.fillText(label, bx + 7, by - 13);
    }
    ctx.globalAlpha = 1;

    // HUD readout
    ctx.font = "500 20px ui-monospace, Menlo, monospace";
    ctx.fillStyle = "rgba(174,184,198,.9)";
    ctx.textBaseline = "alphabetic";
    ctx.fillText("frame " + String(frame % 1000).padStart(3, "0") + "  ·  " + objs.length + " tracks  ·  IDSW 0", 18, 30);
  }

  if (reduce) {
    for (var w = 0; w < 90; w++) step();       // settle into a composed still
    draw();
    return;
  }
  var acc = 0, last = 0;
  function loop(now) {
    if (!last) last = now;
    acc += now - last; last = now;
    while (acc >= 33) { step(); acc -= 33; }    // ~30 fps sim, frame-rate independent
    draw();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
})();
