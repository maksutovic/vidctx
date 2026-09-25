# YouTube and other URLs

Code: `src/vidctx/fetch.py`.

## yt-dlp

- Downloader: [yt-dlp](https://github.com/yt-dlp/yt-dlp), as a Python dependency (`yt-dlp[default]`)
  instead of the Homebrew binary. YouTube breaks yt-dlp every few weeks; `uv tool upgrade vidctx`
  pulls the fix without touching anything else.
- Since late 2025, yt-dlp needs a JavaScript runtime for YouTube (the `yt-dlp-ejs` component, which
  `[default]` includes). **deno** is installed (`/opt/homebrew/bin/deno`) and is picked up
  automatically. If downloads start failing with signature/"n challenge" errors, check deno first.
- Format: `bv*[height<=720][ext=mp4]+ba[ext=m4a]/...`. 720p is plenty because stills are scaled
  to 1280 wide; mp4 + m4a merge by remux (no re-encode). Sizes seen: 21 min talk 57 MB, 45 min
  lecture 214 MB.
- Downloads are cached in `~/.cache/vidctx/downloads/<id>.mp4`; a re-run skips the download.
  Delete them by hand when disk is tight.
- Metadata kept in `transcript.md`: title, channel, URL, and **chapters** (the uploader's chapter
  list becomes `##` sections of the transcript table).

## Captions: ignored on purpose

YouTube captions are available but vidctx always transcribes the audio with Parakeet:
- Auto-captions have no punctuation or sentences, and sentence starts are the backbone of frame
  picking.
- Manual captions are cue-based (screen-sized chunks), not sentences.
- Parakeet is fast enough not to matter: 21 min in 18 s, 45 min in 33 s.

## How lectures differ from screen recordings

| | Screen recordings | Lectures / talks |
|---|---|---|
| Picture changes | constantly (cursor, clicks, scroll) | rarely (slide held for minutes) or constantly (filmed camera) |
| Length | ~10 min | 20-90 min |
| "this" / "here" | the pixel under the cursor | something on the slide or board; still useful |
| click / scroll words | useful | rare, harmless |
| Layout | one screen | slides + speaker camera window + cuts to stage |

That's why URLs default to `--mode lecture`: see [frame-picking.md](frame-picking.md), changes 2 and 3.
