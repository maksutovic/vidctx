"""vidctx <video-or-url>: transcribe locally, pick frame timestamps from the narration,
extract stills, write transcript.md + manifest.json for an LLM to read one still at a time."""
import argparse
import json
import sys
import time
from pathlib import Path

from vidctx import fetch, frames, picks, transcribe

CACHE = Path.home() / ".cache" / "vidctx"
# threshold: fraction of pixels that must change vs a recent kept still for a new still to be kept.
# screen: drop only exact repeats (cursor moves count). lecture: ignore the speaker camera window
# and compare against the last 3 kept stills (slide -> stage shot -> same slide).
MODES = {
    "screen": {"threshold": 0.002, "lookback": 1, "mask_volatile": False},
    "lecture": {"threshold": 0.02, "lookback": 3, "mask_volatile": True},
}
# Filmed footage (whole frame always changing) can't be deduped by pixels; space stills out instead.
CAMERA_SPACING = 15


def mmss(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def load_transcript(video, info, out, redo):
    path = out / "transcript.json"
    if path.exists() and not redo:
        return json.loads(path.read_text()), True
    if not info["has_audio"]:
        return transcribe.empty(path), False
    return transcribe.transcribe(video, path), False


def choose_seconds(video, doc, duration, spacing):
    chosen = picks.thin(picks.pick(doc["utterances"], doc["words"], duration), spacing)
    # Silent stretches: stills where the picture changes, then even spacing for whatever is left.
    for a, b in picks.gaps(chosen, duration):
        last = a
        for t in frames.scene_changes(video, a, b):
            s = picks.sec(t)
            if s - last >= picks.MAX_GAP / 2 and b - s >= picks.MAX_GAP / 2:
                chosen.setdefault(s, []).append("scene")
                last = s
    for a, b in picks.gaps(chosen, duration):
        for s in picks.fill_evenly(a, b):
            chosen.setdefault(s, []).append("gap")
    return chosen


def write_transcript_md(path, meta, info, doc, mode):
    lines = [f"# {meta.get('title') or Path(meta['source']).name}", ""]
    lines += [f"- source: {meta['source']}"]
    if meta.get("channel"):
        lines += [f"- channel: {meta['channel']}"]
    lines += [f"- video: {info['width']}x{info['height']}, {info['fps']} fps, {mmss(info['duration'])} "
              f"({info['duration']:.1f} s)",
              f"- transcript: {doc['engine']} ({len(doc['utterances'])} utterances), mode: {mode}", ""]
    chapters = list(meta.get("chapters") or [])

    def table_head():
        return ["| Start | mm:ss | Utterance |", "|---:|---:|---|"]

    if not chapters:
        lines += table_head()
    for u in doc["utterances"]:
        while chapters and chapters[0]["start"] <= u["start"] + 0.5:
            c = chapters.pop(0)
            lines += ["", f"## {c['title']} ({mmss(c['start'])})", ""] + table_head()
        text = u["text"].replace("|", "\\|")
        lines.append(f"| {u['start']:.1f} | {mmss(u['start'])} | {text} |")
    path.write_text("\n".join(lines) + "\n")


def build_manifest(kept, seconds, reasons, stills, doc, duration, same_as):
    entries = []
    for n, i in enumerate(kept):
        t = seconds[i]
        until = seconds[kept[n + 1]] if n + 1 < len(kept) else duration
        dropped = range(i + 1, kept[n + 1] if n + 1 < len(kept) else len(seconds))
        folded = [seconds[j] for j in dropped if same_as.get(j, i) == i]
        # Dropped because the picture went back to an earlier kept still, not this one.
        returns = [{"t": seconds[j], "same_as": seconds[same_as[j]]} for j in dropped if same_as.get(j, i) != i]
        u = picks.utterance_at(doc["utterances"], t)
        entries.append({
            "t": t,
            "mmss": mmss(t),
            "frame": str(stills[i]),
            "why": reasons[t],
            "utterance_start": u["start"] if u else None,
            "utterance": u["text"] if u else None,
            # Everything said while this still is the current picture (until the next kept still).
            "until": round(until, 1),
            "said": [{"start": x["start"], "text": x["text"]} for x in picks.said_between(doc["utterances"], t, until)],
            **({"folded": folded} if folded else {}),
            **({"returns": returns} if returns else {}),
        })
    return entries


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vidctx", description=__doc__)
    ap.add_argument("source", help="video file or URL")
    ap.add_argument("--out", type=Path, help="output folder (default ~/.cache/vidctx/runs/<name>)")
    ap.add_argument("--mode", choices=MODES, help="screen (default for files) keeps nearly every still; "
                                                   "lecture (default for URLs) drops near-duplicates")
    ap.add_argument("--dedupe", type=float, help="override the near-duplicate threshold (fraction of pixels changed)")
    ap.add_argument("--spacing", type=float, default=picks.MIN_SPACING,
                    help=f"minimum seconds between stills (default {picks.MIN_SPACING}; lower = more stills)")
    ap.add_argument("--width", type=int, default=1280, help="still width in px (default 1280)")
    ap.add_argument("--contact", action="store_true", help="also write contact.jpg")
    ap.add_argument("--retranscribe", action="store_true", help="ignore a cached transcript.json")
    args = ap.parse_args(argv)

    t0 = time.time()
    if fetch.is_url(args.source):
        print(f"downloading {args.source} ...", file=sys.stderr)
        video, meta = fetch.download(args.source, CACHE / "downloads")
        name = meta["id"]
    else:
        video = Path(args.source).expanduser().resolve()
        if not video.exists():
            sys.exit(f"vidctx: no such file: {video}")
        meta = {"source": str(video)}
        name = video.stem
    mode = args.mode or ("lecture" if fetch.is_url(args.source) else "screen")
    out = (args.out or CACHE / "runs" / name).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    info = frames.probe(video)
    doc, cached = load_transcript(video, info, out, args.retranscribe)
    took = "cached" if cached else f"{doc['runtime_s']} s"
    print(f"transcript: {len(doc['utterances'])} utterances ({took})", file=sys.stderr)

    reasons = choose_seconds(video, doc, info["duration"], args.spacing)
    seconds = sorted(reasons)
    frames_dir = out / "frames"
    for old in frames_dir.glob("f*.jpg"):
        old.unlink()
    stills = frames.extract(video, seconds, frames_dir, info["duration"], args.width)
    opts = dict(MODES[mode], **({"threshold": args.dedupe} if args.dedupe is not None else {}))
    kept, same_as, camera = frames.dedupe(stills, **opts)
    if camera:
        spaced = picks.thin(reasons, CAMERA_SPACING)
        kept = [i for i, s in enumerate(seconds) if s in spaced]
        print(f"filmed footage (whole frame keeps changing): spacing stills {CAMERA_SPACING} s apart",
              file=sys.stderr)
    for i in set(range(len(stills))) - set(kept):
        stills[i].unlink()

    manifest = build_manifest(kept, seconds, reasons, stills, doc, info["duration"], same_as)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    write_transcript_md(out / "transcript.md", meta, info, doc, mode)
    if args.contact:
        frames.contact_sheet(video, out / "contact.jpg", info["duration"])

    per = info["duration"] / max(1, len(kept))
    print(f"stills: {len(kept)} kept of {len(seconds)} picked (1 per {per:.1f} s), mode {mode}", file=sys.stderr)
    print(f"done in {time.time() - t0:.1f} s", file=sys.stderr)
    print(out / "manifest.json")


if __name__ == "__main__":
    main()
