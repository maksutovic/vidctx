# Speech-to-text shootout

Which transcriber should feed the frame picker? Priorities, in order: accurate context, local, free.
The full original handoff is in [handoff-stt-shootout.md](handoff-stt-shootout.md); this is the
condensed record. Code lives in [`shootout/`](../shootout).

## Setup

- Test clip: a 10:31 narrated screen recording (Screen Studio, 1156x720, 24 fps) of a web app
  walkthrough. Private client material, so the clip and its transcripts are not committed.
- Reference: Deepgram Nova-3 with `utterances=true` (the transcriber the original manual process
  used). It's a reference, not ground truth.
- Machine: M4 Pro, 48 GB.

Two measurements:
1. `compare.py`: word agreement with Deepgram, word-start deltas, and how often the rounded second
   (the frame the pipeline grabs) is the same.
2. `onset_check.py`: for 56 moments where speech starts after a pause, the error against where
   speech actually starts in the audio. This is the closest thing to ground truth we had.

## Results

| Engine | Where | Cost | Speed (10:31 clip) | Median onset error | Word agreement vs Deepgram |
|---|---|---|---|---|---|
| Deepgram Nova-3 | cloud | paid | n/a | 150 ms | (reference) |
| **Parakeet TDT 0.6B v2** (parakeet-mlx) | local | free | **8.2 s** | 155 ms | 94-97% |
| Speechmatics Melia-1 | cloud | $0.13/hr | n/a | **50 ms** | 94-97% |
| CrisperWhisper 2.0 | local | free, weights non-commercial | 134 s (16x slower) | 50-60 ms | 94-97% |

## Why Parakeet won

- Frame picks round to whole seconds, so sub-second precision barely matters. Parakeet's word
  starts land on the same second as Deepgram's 91% of the time.
- Of 103 matched pointing words ("this", "these", "here", "that", "there"), only 1 was more than
  0.5 s off. Those are the words that decide the most important stills.
- Local, free, and ~77x real time on Apple Silicon.

## Discoveries

- **Don't split Parakeet's output on pauses.** TDT word durations run right up to the next word,
  so there are essentially no gaps between words; Deepgram's 0.8 s pause rule produces nothing
  useful. Use Parakeet's own sentence segmentation (`result.sentences`) as the utterances:
  141 sentences on the test clip vs Deepgram's 162 pause-split fragments.
- Deepgram is ~100 ms late at the start of speech after a pause.
- CrisperWhisper needed `device="mps"` and `transformers<5` to run at all on the Mac.

## Rejected / parked

- **CrisperWhisper 2.0:** non-commercial weights, 16x slower. Environment and model deleted
  (2026-09-24); `shootout/requirements-crisper.txt` rebuilds the environment if ever needed.
- **Deepgram:** the paid baseline, and late on speech onsets.
- **Speechmatics Melia-1:** most accurate onsets and does speaker labels, but cloud. Parked as the
  fallback for multi-speaker recordings (use `model: melia-1, language: multi`, split utterances
  at pauses >= 0.4 s). Not wired into vidctx; `transcript.json` keeps the same words/utterances
  shape as the shootout so it can be added as an engine later.

## Re-running the shootout

The shootout environments were deleted to save disk. To rebuild one:

```bash
cd shootout
uv venv .venv-parakeet --python 3.11
uv pip install --python .venv-parakeet/bin/python -r requirements-parakeet.txt
.venv-parakeet/bin/python run_parakeet.py <video>   # -> out/<stem>.parakeet.json
```

`compare.py` needs a Deepgram reference in `golden/`, and `run_speechmatics.py` reads
`SPEECHMATICS_API_KEY` from `.env.local`.
