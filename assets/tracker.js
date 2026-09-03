/* VisionTrack — the from-scratch tracker, ported to the browser.
 *
 * This is the SAME algorithm the Python study runs, re-implemented in plain JS so
 * it can run live on a webcam with no server: an 8-state constant-velocity Kalman
 * filter (xyah), an O(n^3) Hungarian assignment, ByteTrack two-stage association
 * (high-score match, then recover with the low-score band), and a
 * tentative -> confirmed -> deleted track lifecycle. No tracking library — every
 * line of the association, gating, and lifecycle is here.
 *
 * Exposes window.VT = { ByteTracker }.
 */
(function () {
  "use strict";

  // ---- small dense linear algebra (dims are <=8, so clarity beats cleverness) ----
  function zeros(r, c) {
    var m = new Array(r);
    for (var i = 0; i < r; i++) { m[i] = new Array(c).fill(0); }
    return m;
  }
  function eye(n) {
    var m = zeros(n, n);
    for (var i = 0; i < n; i++) { m[i][i] = 1; }
    return m;
  }
  function matmul(A, B) {
    var r = A.length, k = B.length, c = B[0].length, out = zeros(r, c);
    for (var i = 0; i < r; i++) {
      for (var t = 0; t < k; t++) {
        var a = A[i][t];
        if (a === 0) continue;
        var Bt = B[t];
        for (var j = 0; j < c; j++) { out[i][j] += a * Bt[j]; }
      }
    }
    return out;
  }
  function transpose(A) {
    var r = A.length, c = A[0].length, out = zeros(c, r);
    for (var i = 0; i < r; i++) { for (var j = 0; j < c; j++) { out[j][i] = A[i][j]; } }
    return out;
  }
  function addInto(A, B, sign) {
    for (var i = 0; i < A.length; i++) {
      for (var j = 0; j < A[0].length; j++) { A[i][j] += sign * B[i][j]; }
    }
    return A;
  }
  // Gauss-Jordan inverse of a small square matrix.
  function inv(M) {
    var n = M.length, A = zeros(n, 2 * n), i, j, k;
    for (i = 0; i < n; i++) {
      for (j = 0; j < n; j++) { A[i][j] = M[i][j]; }
      A[i][n + i] = 1;
    }
    for (i = 0; i < n; i++) {
      var piv = i;
      for (k = i + 1; k < n; k++) { if (Math.abs(A[k][i]) > Math.abs(A[piv][i])) piv = k; }
      var tmp = A[i]; A[i] = A[piv]; A[piv] = tmp;
      var d = A[i][i] || 1e-12;
      for (j = 0; j < 2 * n; j++) { A[i][j] /= d; }
      for (k = 0; k < n; k++) {
        if (k === i) continue;
        var f = A[k][i];
        if (f === 0) continue;
        for (j = 0; j < 2 * n; j++) { A[k][j] -= f * A[i][j]; }
      }
    }
    var out = zeros(n, n);
    for (i = 0; i < n; i++) { for (j = 0; j < n; j++) { out[i][j] = A[i][j + n]; } }
    return out;
  }

  // ---- 8-state Kalman filter on [cx, cy, aspect, height] (DeepSORT parameterisation) ----
  var SP = 1 / 20;   // std weight, position
  var SV = 1 / 160;  // std weight, velocity

  function KalmanFilter() {
    this.F = eye(8);
    for (var i = 0; i < 4; i++) { this.F[i][i + 4] = 1; }  // dt = 1
    this.H = zeros(4, 8);
    for (var j = 0; j < 4; j++) { this.H[j][j] = 1; }
  }
  KalmanFilter.prototype.initiate = function (z) {
    var h = z[3];
    var mean = [z[0], z[1], z[2], z[3], 0, 0, 0, 0];
    var s = [2 * SP * h, 2 * SP * h, 1e-2, 2 * SP * h,
             10 * SV * h, 10 * SV * h, 1e-5, 10 * SV * h];
    var cov = zeros(8, 8);
    for (var i = 0; i < 8; i++) { cov[i][i] = s[i] * s[i]; }
    return { mean: mean, cov: cov };
  };
  KalmanFilter.prototype.predict = function (st) {
    var h = st.mean[3];
    var q = [SP * h, SP * h, 1e-2, SP * h, SV * h, SV * h, 1e-5, SV * h];
    var Q = zeros(8, 8);
    for (var i = 0; i < 8; i++) { Q[i][i] = q[i] * q[i]; }
    // mean = F mean  (constant-velocity: position += velocity)
    var mean = new Array(8);
    for (i = 0; i < 8; i++) {
      var acc = 0;
      for (var k = 0; k < 8; k++) { acc += this.F[i][k] * st.mean[k]; }
      mean[i] = acc;
    }
    // cov = F cov F^T + Q
    var cov = addInto(matmul(matmul(this.F, st.cov), transpose(this.F)), Q, 1);
    st.mean = mean; st.cov = cov;
    return st;
  };
  KalmanFilter.prototype.project = function (st) {
    var h = st.mean[3];
    var r = [SP * h, SP * h, 1e-1, SP * h];
    var S = zeros(4, 4);
    for (var i = 0; i < 4; i++) {
      for (var j = 0; j < 4; j++) { S[i][j] = st.cov[i][j]; }
      S[i][i] += r[i] * r[i];
    }
    var mean = [st.mean[0], st.mean[1], st.mean[2], st.mean[3]];
    return { mean: mean, cov: S };
  };
  KalmanFilter.prototype.update = function (st, z) {
    var proj = this.project(st);
    var Sinv = inv(proj.cov);
    // K = cov H^T Sinv  = cov[:, :4] * Sinv   (8x4)
    var covHt = zeros(8, 4);
    for (var i = 0; i < 8; i++) { for (var j = 0; j < 4; j++) { covHt[i][j] = st.cov[i][j]; } }
    var K = matmul(covHt, Sinv);
    var y = [z[0] - proj.mean[0], z[1] - proj.mean[1], z[2] - proj.mean[2], z[3] - proj.mean[3]];
    for (i = 0; i < 8; i++) {
      st.mean[i] += K[i][0] * y[0] + K[i][1] * y[1] + K[i][2] * y[2] + K[i][3] * y[3];
    }
    // cov = cov - K S K^T
    st.cov = addInto(st.cov, matmul(matmul(K, proj.cov), transpose(K)), -1);
    return st;
  };

  // ---- box helpers ----
  function xyxyToXyah(b) {
    var w = b[2] - b[0], h = b[3] - b[1];
    return [b[0] + w / 2, b[1] + h / 2, w / Math.max(h, 1e-6), h];
  }
  function xyahToXyxy(m) {
    var h = m[3], w = m[2] * h, cx = m[0], cy = m[1];
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2];
  }
  function iou(a, b) {
    var x1 = Math.max(a[0], b[0]), y1 = Math.max(a[1], b[1]);
    var x2 = Math.min(a[2], b[2]), y2 = Math.min(a[3], b[3]);
    var iw = Math.max(0, x2 - x1), ih = Math.max(0, y2 - y1);
    var inter = iw * ih;
    var ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
    return ua > 0 ? inter / ua : 0;
  }

  // ---- Hungarian (Munkres) — square/rectangular via padding, O(n^3) ----
  function hungarian(cost) {
    var rows = cost.length, cols = cost[0] ? cost[0].length : 0;
    if (rows === 0 || cols === 0) return [];
    var n = Math.max(rows, cols), BIG = 1e9;
    var C = zeros(n, n);
    for (var i = 0; i < n; i++) {
      for (var j = 0; j < n; j++) {
        C[i][j] = (i < rows && j < cols) ? cost[i][j] : BIG;
      }
    }
    var u = new Array(n + 1).fill(0), v = new Array(n + 1).fill(0);
    var p = new Array(n + 1).fill(0), way = new Array(n + 1).fill(0);
    for (i = 1; i <= n; i++) {
      p[0] = i;
      var j0 = 0;
      var minv = new Array(n + 1).fill(Infinity);
      var used = new Array(n + 1).fill(false);
      do {
        used[j0] = true;
        var i0 = p[j0], delta = Infinity, j1 = -1;
        for (var j = 1; j <= n; j++) {
          if (used[j]) continue;
          var cur = C[i0 - 1][j - 1] - u[i0] - v[j];
          if (cur < minv[j]) { minv[j] = cur; way[j] = j0; }
          if (minv[j] < delta) { delta = minv[j]; j1 = j; }
        }
        for (j = 0; j <= n; j++) {
          if (used[j]) { u[p[j]] += delta; v[j] -= delta; }
          else { minv[j] -= delta; }
        }
        j0 = j1;
      } while (p[j0] !== 0);
      do { var j2 = way[j0]; p[j0] = p[j2]; j0 = j2; } while (j0);
    }
    var out = [];  // [row, col] pairs within the real (unpadded) region
    for (j = 1; j <= n; j++) {
      var r = p[j] - 1, c = j - 1;
      if (r < rows && c < cols) out.push([r, c]);
    }
    return out;
  }

  // Associate a set of tracks to detections by IoU; returns matches passing the
  // gate plus the leftover indices. `boxOf(track)` yields the track's gate box.
  function associate(tracks, dets, boxOf, iouThresh) {
    var matches = [], uT = [], uD = [];
    if (!tracks.length || !dets.length) {
      return { matches: matches, unmatchedTracks: tracks.map(function (_, i) { return i; }),
               unmatchedDets: dets.map(function (_, j) { return j; }) };
    }
    var cost = zeros(tracks.length, dets.length);
    for (var i = 0; i < tracks.length; i++) {
      var tb = boxOf(tracks[i]);
      for (var j = 0; j < dets.length; j++) { cost[i][j] = 1 - iou(tb, dets[j].box); }
    }
    var pairs = hungarian(cost);
    var mT = {}, mD = {};
    for (var k = 0; k < pairs.length; k++) {
      var ti = pairs[k][0], di = pairs[k][1];
      if (1 - cost[ti][di] >= iouThresh) { matches.push([ti, di]); mT[ti] = 1; mD[di] = 1; }
    }
    for (i = 0; i < tracks.length; i++) { if (!mT[i]) uT.push(i); }
    for (j = 0; j < dets.length; j++) { if (!mD[j]) uD.push(j); }
    return { matches: matches, unmatchedTracks: uT, unmatchedDets: uD };
  }

  // ---- track ----
  var PALETTE = ["#22d3ee", "#34d399", "#fbbf24", "#f472b6", "#a78bfa", "#60a5fa",
                 "#f87171", "#4ade80", "#e879f9", "#facc15", "#38bdf8", "#fb923c"];
  var _nextId = 1;

  function Track(kf, det) {
    this.kf = kf;
    this.st = kf.initiate(xyxyToXyah(det.box));
    this.id = _nextId++;
    this.color = PALETTE[(this.id - 1) % PALETTE.length];
    this.cls = det.cls;
    this.hits = 1;
    this.age = 1;
    this.timeSinceUpdate = 0;
    this.state = "tentative";   // tentative -> confirmed -> deleted
    this.trail = [];
  }
  Track.prototype.predict = function () {
    this.kf.predict(this.st);
    this.age++;
    this.timeSinceUpdate++;
  };
  Track.prototype.box = function () { return xyahToXyxy(this.st.mean); };
  Track.prototype.update = function (det, nInit) {
    this.kf.update(this.st, xyxyToXyah(det.box));
    this.cls = det.cls;
    this.hits++;
    this.timeSinceUpdate = 0;
    if (this.state === "tentative" && this.hits >= nInit) { this.state = "confirmed"; }
    var b = this.st.mean;
    this.trail.push([b[0], b[1]]);
    if (this.trail.length > 32) this.trail.shift();
  };

  // ---- the tracker ----
  function ByteTracker(opts) {
    opts = opts || {};
    this.kf = new KalmanFilter();
    this.tracks = [];
    this.trackThresh = opts.trackThresh != null ? opts.trackThresh : 0.5;  // high/low split
    this.detThresh = opts.detThresh != null ? opts.detThresh : 0.1;        // discard below
    this.matchThresh = opts.matchThresh != null ? opts.matchThresh : 0.2;  // IoU gate, high
    this.lowThresh = opts.lowThresh != null ? opts.lowThresh : 0.5;        // IoU gate, low
    this.nInit = opts.nInit != null ? opts.nInit : 3;
    this.maxAge = opts.maxAge != null ? opts.maxAge : 30;
    this.frame = 0;
    this.totalIds = 0;
  }

  // dets: [{ box:[x1,y1,x2,y2], score, cls }]  ->  active confirmed tracks
  ByteTracker.prototype.update = function (dets) {
    this.frame++;
    var i, t;
    for (i = 0; i < this.tracks.length; i++) { this.tracks[i].predict(); }

    var high = [], low = [];
    for (i = 0; i < dets.length; i++) {
      var d = dets[i];
      if (d.score < this.detThresh) continue;
      (d.score >= this.trackThresh ? high : low).push(d);
    }

    // -- stage 1: all tracks vs high-score detections --
    var boxOf = function (tr) { return tr.box(); };
    var pool = this.tracks.slice();
    var a1 = associate(pool, high, boxOf, this.matchThresh);
    for (i = 0; i < a1.matches.length; i++) {
      pool[a1.matches[i][0]].update(high[a1.matches[i][1]], this.nInit);
    }
    var remaining = a1.unmatchedTracks.map(function (idx) { return pool[idx]; });

    // -- stage 2: still-unmatched tracks vs low-score detections (the ByteTrack idea) --
    var a2 = associate(remaining, low, boxOf, this.lowThresh);
    for (i = 0; i < a2.matches.length; i++) {
      remaining[a2.matches[i][0]].update(low[a2.matches[i][1]], this.nInit);
    }

    // -- lifecycle: age out the losers, confirm the keepers, spawn from fresh high dets --
    var lost = a2.unmatchedTracks.map(function (idx) { return remaining[idx]; });
    var kept = [];
    for (i = 0; i < this.tracks.length; i++) {
      t = this.tracks[i];
      if (lost.indexOf(t) !== -1) {
        if (t.state === "tentative" || t.timeSinceUpdate > this.maxAge) { continue; }  // delete
      }
      kept.push(t);
    }
    for (i = 0; i < a1.unmatchedDets.length; i++) {
      kept.push(new Track(this.kf, high[a1.unmatchedDets[i]]));
      this.totalIds++;
    }
    this.tracks = kept;

    var out = [];
    for (i = 0; i < kept.length; i++) {
      t = kept[i];
      if (t.state === "confirmed" && t.timeSinceUpdate < 1) { out.push(t); }
    }
    return out;
  };

  ByteTracker.prototype.reset = function () {
    this.tracks = []; this.frame = 0; this.totalIds = 0; _nextId = 1;
  };

  window.VT = { ByteTracker: ByteTracker, iou: iou, hungarian: hungarian, KalmanFilter: KalmanFilter };
})();
