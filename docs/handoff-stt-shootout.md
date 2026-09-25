> Handoff written at the end of the STT shootout (2026-09-24), kept as-is. File paths refer to
> `shootout/`. Condensed version: [stt-shootout.md](stt-shootout.md).

# Handoff: video → frames + transcript skill for Claude Code

## Goal
Build a Claude Code skill: give it a video (narrated screen recording, .mp4/.mov). It transcribes locally, picks frame timestamps from the transcript, extracts stills, and writes a manifest, so the agent can read the video frame by frame with the matching narration. The manual process is in `inital-prompt.md` (steps: probe → flatten transcript → pick timestamps → extract stills → manifest.json → read one still per call). Priorities: accurate context, local, free.

## Decision so far
- **Transcriber: NVIDIA Parakeet TDT 0.6B v2, run through `parakeet-mlx` on Apple Silicon.** It's free and ran 10:31 of video in 8.2 s on an M4 Pro.
- Precise timestamps don't matter much for this pipeline. Frame picks round to whole seconds, and Parakeet's word starts land on the same second as Deepgram's 91% of the time. Of 103 matched pointing words ("this", "these", "here", "that", "there"), only 1 was more than 0.5 s off.
- **Use Parakeet's own sentence splitting as the utterances** (`result.sentences`: 141 sentences on the test video vs Deepgram's 162 pause-split fragments). Do NOT split on pauses between words: Parakeet leaves no gaps between words.
- Fallback for recordings with several speakers or where speaker labels are needed: Speechmatics Melia-1 (`model: melia-1, language: multi`, $0.13/hr), splitting utterances at pauses ≥0.4 s.
- Rejected: CrisperWhisper 2.0 (weights are non-commercial only; 16× slower than Parakeet); Deepgram (the expensive baseline, and about 100 ms late at the start of speech after a pause).

## Shootout results (test clip: a private 10:31 screen recording, not in the repo)
Accuracy vs where speech actually starts in the audio (`onset_check.py`, 56 moments after a pause), median error: Deepgram 150 ms, Parakeet 155 ms, Melia-1 50 ms, CrisperWhisper 50–60 ms. Words matching Deepgram's: 94–97% for all three.

## Files (all in `shootout/`)
- `common.py`: shared output format + `to_wav` (16 kHz mono) + `words_to_utterances(gap)`
- `run_parakeet.py`: `.venv-parakeet/bin/python run_parakeet.py <video>` → `out/<stem>.parakeet.json` (words + sentence utterances)
- `run_crisper.py`: needs `device="mps"` and `transformers<5` (both already set)
- `run_speechmatics.py`: reads `SPEECHMATICS_API_KEY` from `.env.local` (in `shootout/` or the project root)
- `load_deepgram.py`, `compare.py` (agreement with Deepgram), `onset_check.py` (accuracy against the audio)
- `golden/deepgram.json`: Deepgram Nova-3 reference transcript for the test clip
- Environments: `.venv-parakeet` (parakeet-mlx), `.venv-crisper` (crisperwhisper + torch). Models are in `~/.cache/huggingface`.

## Environment notes
- macOS, M4 Pro, 48 GB RAM. The disk is nearly full (about 11–17 GB free). The CrisperWhisper environment and model (about 4 GB) can be deleted.
- ffmpeg is at ~/.local/bin/ffmpeg; uv is available.

## Next step (agreed direction, not started)
Build the skill (e.g. `.claude/skills/video-context/`): a script that takes a video, runs Parakeet, and writes `transcript.md` (Start | utterance) from its sentences. It then picks timestamps using the rules in `inital-prompt.md`: every utterance start; plus a still for pointing words like "this"/"here" using word-level times; a mid-utterance still for utterances over 8 s; and one for narrated clicks/scrolls (target about 1 frame per 8 s). Finally it extracts 1280-wide JPEGs to a scratch `frames/` folder and writes `manifest.json` as [{t, frame, utterance_start, utterance}]. The skill's instructions then tell the agent to read the stills one at a time, each with its paired utterance. Open question to discuss: the skill layout, and whether to keep the Speechmatics option.
