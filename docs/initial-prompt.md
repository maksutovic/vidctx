> Original manual process this project automates, kept verbatim. The end of the file (step 7
> onward) was garbled when pasted; steps 1-6 are intact. See [frame-picking.md](frame-picking.md)
> for how vidctx's rules differ from step 3.

You convert a narrated screen recording plus a timestamped transcript into a frame-per-utterance evidence set that a multimodal model reads one still at a time.

INPUTS
- video: .mp4 or .mov (Screen Studio / QuickTime). The worked example was 10:31, 1156x720, 24 fps.
- transcript: Deepgram JSON from `utterances=true` (nova-3, diarize on) OR an SRT/VTT OR a TranscriberMac export with timestamps. Word-level timings are welcome but the unit of work is the utterance.
- Fallback when no transcript is given: `uvx whisper-ctranslate2 <video> --model small --output_format srt` (no repo dependency).

STEP 1: PROBE
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,duration -of default=nw=1 <video>
Record width, height, fps and duration in the output header.

STEP 2: FLATTEN THE TRANSCRIPT
From Deepgram JSON take results.utterances[] and keep (start, end, transcript). Do not use the channel-level paragraph text; the utterance boundaries are the timeline.
Write transcript.md as a two-column table: Start (seconds, one decimal) | verbatim utterance. Keep the transcriber's sentence grouping and filler; do not clean it up.
For SRT/VTT, one cue = one row.

STEP 3: PICK FRAME TIMESTAMPS (the part that matters)
Start from every utterance start time, rounded to the nearest second.
Then add stills when: the speaker uses a demonstrative ("this picture", "this headline", "here", "look at all this"), the utterance is longer than ~8 s (add one mid-utterance still), or a click or scroll is narrated ("let me click", "moving down"). Drop nothing; ~1 frame per 8 s of video is the target. The 10:31 example produced 75 stills.
Never use fixed-cadence fps=1/2 as the primary pass; it puts the still between the sentence and the thing it points at. Scene-change detection (select='gt(scene,0.3)') is a supplement for long silent stretches, not a replacement.

STEP 4: EXTRACT ONE STILL PER TIMESTAMP
for t in <timestamps>; do
  ffmpeg -v error -y -ss $t -i <video> -frames:v 1 -vf "scale=1280:-2" -q:v 3 frames/f$(printf %03d $t).jpg
done
Notes: -ss before -i seeks by keyframe and is fast; 1280 wide keeps UI text legible while staying ~40 KB per JPEG; -q:v 3 is the quality knob. Name the file by its second so the model can cite mm:ss without a lookup. Keep frames out of the repo (scratch dir).

STEP 5: BUILD THE MANIFEST
Write manifest.json: an array of {t, frame, utterance_start, utterance} pairing each still with the utterance it was taken under (the nearest utterance whose start <= t). This is the only file the reader needs besides the images.

STEP 6: READ
Read the stills in time order, one image per read call, with the paired utterance in front of you. Do not batch ten frames into one look; the alignment of "this" to the pixel under the cursor is lost when frames are read as a grid. For each still write three things: what is on screen (page, section open, cursor target, visible text), what was said over it, and what surface it maps to. Then produce the walkthrough table (Time | On screen | What was asked | Surface it map, citing mm:ss.

STEP 7: A CONTACT SHEET (option
ffmpeg -i <video> -vf "fps=1/10,scale=320:-2,tile=6x11" -frames:v 1 contact.jpg
Useful for the person to spot-ceads the individual stills, not
this.

OUTPUT LAYOUT
walkthrough/
  transcript.md      (committed
  walkthrough.md     (committed, the table plus playback sections)
frames/              (scratch, not committed: f002.jpg ... f629.jpg)                    nifest.json        (scratch)
                                                                                        e three mechanics that carrie
                                                                                        Timestamps come from the trans landed on utterance starts plus the demonstrative moments, so "this picture" resolved to the pixel under the cursor.  One still per read call, in tnce paired. Seventy-fivesequential image reads, each with the sentence spoken over it. Batching frames into a grid loses that pairing.
- Modest stills. 1280 wide, JPE each, named by second. Enough to read UI text and small enough to read all of them.
