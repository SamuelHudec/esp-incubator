# TinyFace: a simpler experiment plan

Reviewed: 2026-10-30. **Proposal for discussion.**

**First diagnose the current model, then improve its training data, then try one
architecture change if needed.** Start small and let the results choose the next
experiment. The [technical reference](architecture-reference.md) holds the details
and primary research sources.

## Our starting point

The model reads a **128×96 grayscale image** and predicts a face score and box
at each cell of a **16×12 grid**. It has 5,085 trainable parameters, about 1.20
million MACs and a theoretical 63×63 receptive field. INT8 activation buffers
use 49,152 bytes; camera buffers are additional. Historical total inference was
350–370 ms, about 2.5 inferences/s, separately from video FPS.

Two important uncertainties: we do not know which checkpoint produced the board
measurements, and teacher-label scores do not establish real-camera accuracy.
The model already learns background cells inside face images. Missing whole
images without faces may affect false alarms; they do not by themselves explain
weak scores on real faces in darkness.

## 1. Find the failure — no new training

Choose a known checkpoint and matching INT8 export. Start with roughly **60–100
varied real-camera development images**: bright/dim faces, different face sizes
and empty scenes, from separate capture sessions. Manually check every face box.
Inspect the original JPEG and the actual 128×96 grayscale input.

Keep training, development and a final holdout separate. Reserve final-test
sessions before tuning. Adjacent frames, near duplicates, crops and paired light
settings stay together. Hold out people where feasible; otherwise state that
results do not establish generalization to unseen people. The same room need not
make every session one group, but near-identical scenes must not cross splits.

Compare float and INT8 from the **same checkpoint** on those images. Count faces
found/missed, false boxes and empty images with detections. Break results down
by light and face size. Check thresholds .30/.50, then compare the tradeoff between
recall and false alarms. A score shift alone is not a loss of detection quality.

| Observation | Next action |
|---|---|
| Float works, INT8 is clearly worse | Check preprocessing and calibration first. |
| Both miss faces still visible at 128×96 | Test real training images in step 2. |
| False detections dominate | Prioritize verified empty training scenes. |
| Darkness, blur or clipping removes detail | Investigate capture conditions before expecting a larger model to fix it. |
| Desktop and board disagree | Verify checkpoint identity and the image/inference pipeline. |

**Result:** a small comparison table and representative failures. This pilot can
guide an experiment; it cannot establish a reliable 1% false-alarm rate. A combined
float/INT8 report needs a small future evaluation task, not a large framework.

## 2. Test the data explanation

For real-camera misses, compare two runs from scratch:

- **A: reference** — the current synthetic training set with a fixed label policy.
- **B: real-data mix** — replace about 25% of A's training images with reviewed
  real-camera face images; keep the total number of training images unchanged.

Use a smaller recorded fraction if independent real images are scarce. Keep
architecture, epochs, batch size, LR schedule, augmentation, validation,
checkpoint-selection rule and seed fixed. Equal-length manifests work with the
existing trainer; a new sampler or scheduler is unnecessary. Compare float first;
for the later INT8 comparison use the same recorded calibration images.

If false alarms dominate, instead make a separate comparison replacing some
training images with **confirmed empty scenes** (`boxes: []`). A teacher miss is
not a verified negative. Do not combine real-face replacement and negative-image
replacement in the first trial; replacing positives also reduces their exposure.

**Keep a candidate** if it finds more real faces at comparable false alarms, or
reduces false alarms without losing useful recall. Inspect bright/dim failures;
repeat a promising pair with another seed. Small or inconsistent gains require
more evidence, not a fixed “+3%” pass mark.

**Cost:** annotation and matched training runs; deployed network compute/RAM stay
the same. The current trainer starts from scratch, without a fine-tuning option.

## 3. Try one architecture change if needed

If label and training checks still suggest insufficient capacity, first test
**32→48 channels in the final three blocks**. Spatial geometry stays the same
and existing C convolution operators remain usable. MACs increase by about 53%;
actual latency must be measured.

For specifically small-face failures, test **160×120 input** instead. For mainly
large-face/context failures, consider **one extra final block** instead. Choose
one based on evidence. Assignment, loss, separate heads and distillation stay
in the [optional reference](architecture-reference.md), with costs and stop rules.

**Stop before C integration if the Python result has no repeatable real-development
gain.** A promising candidate proceeds to INT8 parity and measured board latency/RAM.
New shapes/topologies require explicit architecture IDs and coordinated exporter/C
changes. Evaluate the selected candidate and threshold on the sealed holdout before
deployment; if its results guide further tuning, reserve a fresh final holdout.

## The next action

**Start with step 1: existing float versus INT8 on saved camera images.** The likely
second experiment is the real-data mix; negatives take priority only if false
alarms dominate. Select the third from the remaining failure.

Keep light settings at the current 25% cap / step 8 and record capture conditions.
Manual captures and Auto-mode operation differ. Freeze runtime optimizations for
model comparisons; neither accuracy nor FPS is promised. This revision changes
only documentation. See the [experiment log](experiment-log.md) for observations
and the [reference](architecture-reference.md) for implementation/export details.
