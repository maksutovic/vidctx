# vidctx

Let Claude Code *watch* a video. `vidctx` takes a narrated screen recording or a YouTube
lecture, transcribes it locally, picks the moments worth looking at from what's being said,
extracts stills at those moments, and writes a manifest pairing each still with its narration.
A Claude Code skill (`video-context`) then reads the stills one at a time, each with the words
spoken over it, so "click **this**" lines up with what's under the cursor.

Local and free: transcription runs on Apple Silicon with NVIDIA Parakeet (via parakeet-mlx), and
frames come from ffmpeg. No API keys.

```bash
vidctx ~/Downloads/walkthrough.mp4
vidctx "https://www.youtube.com/watch?v=1rMgw0Q5MgY"
```

## Install

Requires a Mac with Apple Silicon. Prerequisites, if you don't have them:

```bash
brew install uv ffmpeg deno
```

**1. The tool** (puts `vidctx` on your `PATH`):

```bash
uv tool install git+https://github.com/maksutovic/vidctx
```

**2. The Claude Code skill**, pick one:

```bash
vidctx install-skill              # all projects: ~/.claude/skills/video-context
vidctx install-skill --project    # this repo only: <repo>/.claude/skills/video-context (commit it to share)
```

Start a new Claude Code session, then ask it to watch a video file or YouTube link. The first run
downloads the Parakeet model (~2.4 GB, into `~/.cache/huggingface`).

**Update:** `uv tool upgrade vidctx`, then re-run `vidctx install-skill` so the skill matches.
**Uninstall:** `uv tool uninstall vidctx` and delete the `video-context` skill folder.

### Developing

```bash
git clone https://github.com/maksutovic/vidctx && cd vidctx
uv tool install --editable . --python 3.11
ln -s "$PWD/src/vidctx/skill" ~/.claude/skills/video-context
```

With `--editable` and the symlink, code and skill changes apply immediately everywhere.
(`install-skill` refuses to overwrite a symlinked skill folder, so a dev link stays put.) The skill's
source is `src/vidctx/skill/SKILL.md`, which ships inside the package; `.claude/skills/video-context`
in this repo is a symlink to it.

## Usage

```
vidctx <file-or-url> [--out DIR] [--mode screen|lecture] [--spacing S] [--dedupe F]
                     [--width PX] [--contact] [--retranscribe]
```

| Flag | Default | What it does |
|---|---|---|
| `--out` | `~/.cache/vidctx/runs/<name>` | output folder (the skill passes a session scratch dir) |
| `--mode` | `screen` for files, `lecture` for URLs | how aggressively repeated pictures are dropped |
| `--spacing` | 4 | minimum seconds between stills; lower = more stills |
| `--dedupe` | 0.002 screen / 0.02 lecture | fraction of pixels that must change to keep a still |
| `--width` | 1280 | still width (never upscales) |
| `--contact` | off | also write `contact.jpg`, a thumbnail grid for a human to skim |
| `--retranscribe` | off | ignore the cached `transcript.json` |

Re-runs reuse the cached transcript, so tuning `--spacing` / `--dedupe` takes seconds.

### Output

```
<out>/
  transcript.json   raw Parakeet words + sentences (the cache)
  transcript.md     header (source, resolution, fps, duration) + Start | mm:ss | Utterance table,
                    split into sections by YouTube chapters when present
  manifest.json     one entry per still, in time order
  frames/f0034.jpg  stills named by second
  contact.jpg       with --contact
```

A manifest entry:

```json
{
  "t": 34, "mmss": "0:34",
  "frame": "/…/frames/f034.jpg",
  "why": ["this"],
  "utterance_start": 32.32,
  "utterance": "So, for example, this picture, where does this picture live?",
  "until": 40,
  "said": [{"start": 32.32, "text": "So, for example, this picture, where does this picture live?"}],
  "folded": [36],
  "returns": [{"t": 52, "same_as": 34}]
}
```

- `why`: what triggered the still: `start` (sentence start), a pointing word (`this`, `here`,
  `look at`…), an action (`click`, `scrolling`…), `mid` (inside a long sentence), `scene` / `gap`
  (silent stretch)
- `said`: everything spoken from `t` until the next still. This is what to read alongside the image
- `folded`: picks dropped because the picture didn't change; their narration is in `said`
- `returns`: picks dropped because the picture went back to an earlier still

## How it works

1. **Fetch** (URLs only): yt-dlp downloads ≤720p mp4 plus title, channel and chapters.
2. **Probe**: ffprobe for width, height, fps, duration, audio.
3. **Transcribe**: 16 kHz mono wav → Parakeet TDT 0.6B v2. Words plus Parakeet's own
   sentence segmentation as the utterances. ~1 s per minute of video.
4. **Pick timestamps** from the narration: sentence starts, pointing words ("this", "these",
   "here", "look at", "right there"), narrated actions ("click", "scroll", "go to", "moving
   down"), extra stills inside sentences longer than 8 s, and scene detection for silent stretches
   over 8 s. Rounded to whole seconds and thinned to ≥4 s apart (pointing/action beats sentence
   start beats mid-sentence).
5. **Extract** all candidates in parallel with ffmpeg.
6. **Drop repeated pictures** on 160x90 grayscale thumbnails. Lecture mode ignores the part of
   the frame that is always changing (a speaker camera window) and compares against the last 3
   kept stills; filmed footage, where the whole frame always changes, falls back to one still per
   15 s.
7. **Write** `manifest.json` and `transcript.md`.

The skill ([`src/vidctx/skill/SKILL.md`](src/vidctx/skill/SKILL.md))
runs `vidctx`, reads `transcript.md` for the arc, then reads stills **one per Read call** in time
order with their `said` text, and ends with a Time | On screen | What was said | What it refers to
table citing mm:ss. Batching stills into a grid loses the pairing between "this" and the pixel.

## How we built it

1. **The manual process.** It started as a hand-run recipe ([docs/initial-prompt.md](docs/initial-prompt.md)):
   Deepgram transcript → pick timestamps by hand-applied rules → ffmpeg stills → manifest → read
   one still at a time. It worked (75 stills for a 10:31 walkthrough) but cost money and effort.
2. **STT shootout.** Deepgram, Parakeet, Speechmatics Melia-1 and CrisperWhisper 2.0 on the same
   recording, scored on word agreement and on speech-onset error against the audio. Parakeet
   won: free, local, 8.2 s for 10:31, and 91% of word starts on the same second as Deepgram,
   which is what matters when frames round to whole seconds. Key discovery: split on Parakeet's
   sentences, never on pauses (its word timings leave no gaps). → [docs/stt-shootout.md](docs/stt-shootout.md)
3. **Global CLI instead of a skill-only script.** Same pattern as the `ytscript` tool: a
   Python package installed with `uv tool install --editable`, with a thin skill on top. Python
   because parakeet-mlx only exists there.
4. **Implementing the rules literally gave 223 stills, not 75.** Parakeet emits a sentence every
   ~4.5 s. Measuring frame-to-frame change showed it's bimodal (cursor-only vs real change), so no
   duplicate threshold fixes it; a 4 s minimum spacing with priorities lands at 85 (1 per 7.4 s)
   with narration folded, not lost. → [docs/frame-picking.md](docs/frame-picking.md)
5. **YouTube.** yt-dlp for downloads; YouTube captions ignored in favour of Parakeet sentences.
   → [docs/youtube.md](docs/youtube.md)
6. **Lectures broke the dedupe.** A conference talk's speaker camera window and cuts to the stage
   camera kept almost every still; a filmed chalkboard lecture kept all 488. Fixed with a volatility mask
   (ignore pixels that change 2x more often than the frame median), a 3-still lookback, and a
   spacing fallback for filmed footage: 142 → 107 and 488 → 135.

Results on the four test videos, open issues and tuning tables are in
[docs/frame-picking.md](docs/frame-picking.md).

## Repo layout

```
src/vidctx/
  cli.py         entry point: fetch → probe → transcribe → pick → extract → dedupe → write
  fetch.py       yt-dlp download + metadata
  transcribe.py  Parakeet → transcript.json
  picks.py       timestamp rules (pure functions, unit tested)
  frames.py      ffprobe/ffmpeg helpers, scene detection, dedupe, contact sheet
tests/           pytest for picks.py
src/vidctx/skill/SKILL.md    the Claude Code skill (shipped in the package; .claude/skills/video-context links here)
docs/            decisions, measurements, original notes
shootout/        the STT comparison scripts (environments deleted; see docs/stt-shootout.md)
```

## Development

```bash
uv run --python 3.11 --group dev pytest -q
```

Caches: downloads in `~/.cache/vidctx/downloads/`, runs in `~/.cache/vidctx/runs/`. Both are safe
to delete.
