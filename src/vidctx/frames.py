"""ffmpeg/ffprobe helpers: probe, still extraction, scene detection, near-duplicate filtering."""
import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

THUMB = (160, 90)  # grayscale size used to compare stills
PIXEL_DELTA = 12   # a pixel "changed" if its gray value moved more than this (0-255)


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                         check=True, capture_output=True, text=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = v.get("avg_frame_rate", v.get("r_frame_rate", "0/1")).split("/")
    return {
        "width": v["width"], "height": v["height"],
        "fps": round(int(num) / int(den), 2) if int(den) else None,
        "duration": float(v.get("duration") or info["format"]["duration"]),
        "has_audio": any(s["codec_type"] == "audio" for s in info["streams"]),
    }


def frame_name(t, duration):
    return f"f{t:0{max(3, len(str(int(duration))))}d}.jpg"


def extract(video, seconds, frames_dir, duration, width=1280):
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    def one(t):
        dst = frames_dir / frame_name(t, duration)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale='min({width},iw)':-2", "-q:v", "3", str(dst)], check=True)
        return dst

    with ThreadPoolExecutor(8) as pool:
        return list(pool.map(one, seconds))


def scene_changes(video, a, b, threshold=0.3):
    """Seconds in [a, b] where the picture changes (ffmpeg scene score)."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(a), "-to", str(b), "-i", str(video), "-an",
                        "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [a + float(m) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def _thumb(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={THUMB[0]}:{THUMB[1]},format=gray",
                          "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).astype(np.int16)


def _dilate(mask, r=3):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def volatile_mask(thumbs):
    """Pixels that change far more often than the rest of the frame: a speaker camera window
    next to the slides. Per pixel, the share of consecutive stills where it changed; anything
    over twice the frame's median, grown a little to cover the window's edges."""
    changed = np.abs(np.diff(thumbs, axis=0)) > PIXEL_DELTA
    vol = changed.mean(axis=0).reshape(THUMB[1], THUMB[0])
    return _dilate(vol > 2 * np.median(vol)).ravel(), float(np.median(vol))


def dedupe(paths, threshold, lookback=1, mask_volatile=False):
    """Decide which stills to keep. A still is dropped when less than `threshold` of its pixels
    differ from one of the last `lookback` kept stills (lookback > 1 catches slide -> stage shot
    -> same slide). Comparing to kept stills, not the previous candidate, stops slow drift from
    hiding a real change.

    Returns (keep, same_as, camera): kept indices; for each dropped index, the kept index it
    matched; and camera=True when most of the frame changes between most stills (filmed footage),
    where pixel comparison is meaningless and nothing is dropped."""
    with ThreadPoolExecutor(8) as pool:
        thumbs = np.stack(list(pool.map(_thumb, paths)))
    stable = np.ones(thumbs.shape[1], bool)
    if mask_volatile and len(thumbs) > 2:
        masked, median = volatile_mask(thumbs)
        if median > 0.4 or masked.mean() > 0.5:
            return list(range(len(paths))), {}, True
        stable = ~masked
    keep, same_as = [0], {}
    for i in range(1, len(thumbs)):
        for k in reversed(keep[-lookback:]):
            if np.mean((np.abs(thumbs[i] - thumbs[k]) > PIXEL_DELTA)[stable]) < threshold:
                same_as[i] = k
                break
        else:
            keep.append(i)
    return keep, same_as, False


def contact_sheet(video, dest, duration, cols=6, max_tiles=66):
    step = max(10, math.ceil(duration / max_tiles))
    rows = math.ceil(duration / step / cols)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
                    f"fps=1/{step},scale=320:-2,tile={cols}x{rows}", "-frames:v", "1", "-q:v", "4", str(dest)],
                   check=True)
    return step
