---
name: video-context
description: Watch a video — a narrated screen recording (.mp4/.mov) or a YouTube lecture/talk URL — by transcribing it locally and reading timestamped stills paired with what was said over each one. Use when the user shares a video file or video link and wants it reviewed, summarized, turned into specs/notes/tickets, or asks what happens on screen at some point.
---

# Video context

`vidctx` (a global CLI, source in `~/Developer/side-projects/video-claude-code`) turns a video into
stills + narration. It transcribes locally (Parakeet on Apple Silicon, ~1 s per minute of video),
picks frame timestamps from the narration (sentence starts, "this"/"here"/"look at", narrated
clicks/scrolls, long sentences, silent stretches), extracts 1280-wide JPEGs, and drops stills that
show the same picture as one already kept.

## 1. Run it

```bash
vidctx "<file-or-url>" --out "<scratchpad>/vidctx/<short-name>"
```

- Use the session scratchpad for `--out`; never write stills into the user's repo. Without `--out`
  it writes to `~/.cache/vidctx/runs/<name>/`.
- Mode is automatic: local files are `screen` (keeps nearly every distinct still), URLs are
  `lecture` (ignores the speaker's camera window, drops repeated slides; filmed footage falls
  back to one still per ~15 s). Override with `--mode screen|lecture`.
- Density: default is about one still per 7-12 s. `--spacing 2` for more stills on a dense
  screen recording, `--spacing 8` for fewer. Re-runs reuse the cached transcript and take seconds.
- The transcript download/model is cached; the first run of a new video takes ~5-60 s for
  transcription (plus the download for URLs).

It prints the path to `manifest.json`. The output folder holds:
- `transcript.md`: header (source, resolution, fps, duration) and every sentence with its start
  time; YouTube chapters become section headings.
- `manifest.json`: one entry per still, in time order:
  - `t`, `mmss`, `frame` (absolute path), `why` (what triggered the still)
  - `utterance_start`, `utterance`: the sentence being spoken when the still was taken
  - `said`: everything said from `t` until the next still (`until`). Read this, not just `utterance`.
  - `folded`: seconds whose stills were dropped because the picture was unchanged
  - `returns`: seconds where the picture went back to an earlier still (`same_as`)

## 2. Read it

1. Read `transcript.md` once to get the overall arc.
2. Read `manifest.json`, then read the stills **in time order, one image per Read call**, with that
   entry's `said` text in front of you. Never tile or batch stills into a grid; the point is that
   "this" in the narration lines up with what is under the cursor in that exact still.
3. For each still note: what is on screen (page/slide, section, cursor target, visible text), what
   was said over it, and what it refers to.
4. Cite moments as `mm:ss` (the `mmss` field) in everything you write back.

Lecture/talk notes:
- Edited talks cut between slides, a live demo, and the speaker. If a still shows only the speaker
  or the stage, whatever "this" refers to is usually in the next still; read on before concluding.
- Filmed chalkboard lectures carry most of their content in `said`; use the stills for what's on
  the board.

For long videos (100+ stills), tell the user the count before reading them all, and offer to read
only a chapter or time range (filter `manifest.json` by `t`).

## 3. Output

Unless the user asked for something else, finish with a walkthrough table:

| Time | On screen | What was said / asked | What it refers to |
|---|---|---|---|

Optional: `vidctx ... --contact` also writes `contact.jpg` (a thumbnail grid of the whole video)
for the user to skim. It's for them, not a replacement for reading the stills one at a time.
