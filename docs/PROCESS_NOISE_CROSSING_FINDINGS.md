# Process-noise sensitivity: crossing check on two cameras

The earlier [process-noise probe](../experiments/frame_rate_noise_probe_v1_result.json)
counted fewer track births when the Kalman filter's one-step process covariance
was multiplied by 3 or 9. Births are not a measure of accuracy. This follow-up
replayed the **same saved detector proposals** with each scale and scored
crossings using the previously frozen labels, gate geometry, and match window
for each camera. It is a post-hoc diagnostic on cameras already inspected, not
independent validation of a selected setting.

| Camera and input | Q scale | Matched | Missed | Extra | Track births |
| --- | ---: | ---: | ---: | ---: | ---: |
| AICC c002, 10 fps, BGR/bilinear | 1 | 1/5 | 4 | 0 | 180 |
| AICC c002, 10 fps, BGR/bilinear | 3 | 2/5 | 3 | 0 | 137 |
| AICC c002, 10 fps, BGR/bilinear | 9 | 3/5 | 2 | 0 | 99 |
| Hanoi, 30 fps, BGR/bilinear | 1 | 7/16 | 9 | 1 | 137 |
| Hanoi, 30 fps, BGR/bilinear | 3 | 7/16 | 9 | 1 | 105 |
| Hanoi, 30 fps, BGR/bilinear | 9 | 7/16 | 9 | 1 | 80 |

On AICC, the newly matched reference crossings are at frame 132 for 3× and
frames 132 and 145 for 9×. Their same-frame predicted/reference box IoUs are
0.610 and 0.619/0.759 respectively. These checks support the intended-vehicle
interpretation, while leaving full trajectory quality untested. Frames 168
and 199 remain missed. The last is at the clip boundary. On Hanoi, the seven
matched reference frames are unchanged at all three scales; one extra
crossing remains (its frame moves from 479 to 478 at 9×). The default 1×
replay reproduces both frozen baseline scores exactly.

This is a useful mechanism signal, **not** a production calibration: the same
two cameras informed this follow-up, 21 labeled crossings are too few to
estimate field performance, and Q scaling leaves the frame-based transition
matrix, velocity units, track age, and confirmation rules unchanged. The
30 fps birth reduction does not imply a 10 fps-specific fix. There is no
detector change, default change, package release, or claim of improved
real-world traffic counts. The next test should freeze a new camera-separated
comparison and inspect false associations and crossing errors before adopting
any time-aware motion model.

The [machine-readable result](../experiments/process_noise_crossing_v1_result.json)
includes input SHA-256 fingerprints, every matched/missed/extra event frame,
and same-frame overlap. The [replay script](../experiments/process_noise_crossing_replay.py)
uses the private local walkthrough's frozen camera adapters and the saved
detections; it does not rerun the detector or redistribute footage. Run it
with the walkthrough root as its argument in the existing A40/trafficlens
environment. The camera-specific protocols and underlying labels are kept
in that local walkthrough pending media-rights clarification.
