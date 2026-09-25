# Frame picking: rules, tuning data, and why they changed

The original manual process ([initial-prompt.md](initial-prompt.md), step 3) says: a still at every
utterance start, plus stills for pointing words, long utterances and narrated clicks/scrolls;
drop nothing; target ~1 still per 8 s. The 10:31 example produced 75 stills.

Implementing that literally did not reproduce 75, and it broke down on lectures. This is what
changed and the numbers behind each change. Code: `src/vidctx/picks.py`, `src/vidctx/frames.py`.

## Pipeline

1. `picks.pick()`: candidate seconds from the transcript
   - every sentence start
   - pointing words at the word's own start: `this`, `these`, `those`, `here` always; `that` and
     `there` only in phrases (`that one`, `right there`, `over there`, `see that`, `in there`),
     plus `look at`
   - action words: `click*`, `scroll*`, `select*`, `type`, `drag*`, `hover*`, `open*`, `switch*`,
     `expand/collapse`, `toggle`, `zoom`, ... and phrases like `go to`, `go back`, `moving down`
   - sentences longer than 8 s get evenly spaced interior stills so no gap inside exceeds 8 s
     (the spec said one mid-point still; the test clip has 20 such sentences up to 23.6 s long,
     where one still leaves 11 s gaps)
   - everything rounded to the nearest second; picks on the same second merge their reasons
2. `picks.thin()`: minimum spacing (default 4 s), priority pointing/action > start > mid
3. Silent stretches over 8 s: ffmpeg scene detection (`gt(scene,0.3)`) in that stretch, then even
   spacing for whatever is still uncovered
4. Extract every candidate (1280 wide max, never upscaled, `-q:v 3`, named `f<second>.jpg`)
5. `frames.dedupe()`: drop stills that show the same picture as a recent kept still; their
   narration folds into the kept still's `said`
6. `manifest.json`

## Change 1: minimum spacing (why not "every utterance start")

Parakeet produces a sentence every ~4.5 s on the test clip, so the literal rules gave:

| Rule | Picks |
|---|---|
| sentence starts | 137 |
| + pointing / action / long-sentence | 223 total |
| after dropping identical stills | 130 kept (1 per 4.9 s) |

The 75 in the original run must have involved judgement, not the literal rules. Frame-to-frame
change on the walkthrough is bimodal: ~45% of consecutive picks differ by <0.2% of pixels
(only the cursor moved), the rest by >3% (scroll, page change). So no dedupe threshold gets near
75; the screen genuinely changes ~110 times.

Minimum spacing with priority, then exact-duplicate removal:

| Spacing | Picks | Kept | Density |
|---|---|---|---|
| 0 s | 223 | 130 | 1 per 4.9 s |
| 2 s | 163 | 106 | 1 per 6.0 s |
| 3 s | 125 | 91 | 1 per 6.9 s |
| **4 s** | 106 | 80 | 1 per 7.9 s |
| 5 s | 92 | 72 | 1 per 8.8 s |

4 s is the default (85 final with gap fill). No narration is lost: a dropped pick's sentence
still appears in the kept still's `said`. `--spacing 2` when more visual detail matters.

Spot checks: 0:34 "this picture, where does this picture live?" has the cursor on the photo;
2:51 "this [number] needs to be editable" has that number highlighted under the cursor.

## Change 2: dedupe that survives a speaker camera window

Comparison works on 160x90 grayscale thumbnails; a pixel "changed" if its value moved >12/255;
a still is a duplicate if under `threshold` of pixels changed.

**Screen mode** (default for local files): threshold 0.002, compare to the last kept still only.
Drops exact repeats; cursor movement counts as a change.

**Lecture mode** (default for URLs) was first a plain 0.03 threshold. On a conference talk
(slides left, speaker camera window right, cuts to a stage camera) it kept 142 of 227: the
speaker moving defeats pixel comparison, and slide -> stage shot -> same slide keeps the slide
twice.

Fix, measured on that talk (198 candidate stills):
- Per pixel, the share of consecutive stills where it changed ("volatility"). The slide area
  changes in ~20% of pairs (matching the real slide-change rate); the speaker window far more.
- A fixed 0.5 cutoff masked only 2% of the frame (just the core of the window). Masking pixels
  over **2x the frame's median volatility**, dilated by 3 px, covers the whole window (~7%).
- Compare each still against the **last 3 kept** stills, not just the last one.

| Mask (lookback 1, kept of 198) | Threshold 0.01 | 0.02 | 0.03 | 0.04 |
|---|---|---|---|---|
| fixed 0.5 volatility cutoff (2% masked) | 161 | 115 | not run | 96 |
| 2x median, dilated (7% masked) | 108 | 101 | 95 | not run |

Chosen: 2x median mask, threshold 0.02, lookback 3. With gap fill: **107 stills, 1 per 11.9 s**
(17 "returns" to an earlier slide caught by the lookback). A visual check of the kept stills showed
mostly real changes: slide builds, live demo steps, and some stage/speaker shots.

## Change 3: filmed footage falls back to spacing

On a filmed chalkboard lecture (MIT 6.006 lecture 1, 45 min) the median pixel volatility was 0.68:
camera noise and a moving lecturer change most of the frame between any two stills, so nothing
is ever a duplicate (488 of 488 kept). When median volatility > 0.4 or the mask would cover
more than half the frame, vidctx skips pixel dedupe and thins to one still per 15 s instead:
**135 stills, 1 per 20 s**. The narration carries most of the content in that kind of lecture.

## Results summary (2026-09-24)

| Video | Kind | Mode | Stills | Density | Run time |
|---|---|---|---|---|---|
| Profile-builder walkthrough, 10:31 | screen recording | screen | 85 | 7.4 s | 35 s first, <4 s cached |
| David Khourshid, "Goodbye Slop; Welcome Determinism", 21:17 | talk: slides + camera window | lecture | 107 | 11.9 s | 101 s incl. download |
| 3Blue1Brown, "But what is a neural network?", 18:39 | continuous animation | lecture | 142 | 7.9 s | 47 s incl. download |
| MIT 6.006 lecture 1, 45:38 | filmed chalkboard | lecture (camera fallback) | 135 | 20.3 s | 116 s incl. download |

## Known limitations

- **Edited talks cut away.** At 9:11 of the talk, "So here is an example of an email drafter"
  lands on a close-up of the speaker; the demo appears in the next still (9:19). The skill tells
  the reader to read on when a still shows only the speaker. A smarter fix would detect speaker
  shots and nudge the still forward to the next content frame.
- Action words are matched on the word alone, so "open question" or "type of" still trigger a
  still. Cheap false positives; spacing absorbs most of them.
- Picks at a sentence start can inherit a pointing word that ended the previous sentence
  (e.g. 4:15 on the walkthrough). Harmless, but the `why` label can look odd.
- Thresholds are tuned on four videos. Expect to revisit `threshold`, `lookback` and
  `CAMERA_SPACING` for other layouts (e.g. slides with an animated background).
- Continuous-animation videos (3Blue1Brown) change constantly and stay dense; a still every
  ~8 s is probably right for them, but it's a lot of images for a long video.
- The read step (the agent reading 85-140 stills one at a time) has not been tested end to end
  yet. At ~1-1.5k tokens per 1280-wide image, 100 stills is roughly 100-150k tokens of context.
