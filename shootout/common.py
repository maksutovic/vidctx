"""Shared schema for shootout outputs.

Every engine writes out/<engine>.json:
  {"engine", "audio", "runtime_s",
   "words":      [{"word", "start", "end", "speaker"}],
   "utterances": [{"start", "end", "text", "speaker"}]}
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "out"

# Deepgram's utt_split default: a new utterance after 0.8 s of silence between words.
UTT_GAP = 0.8


def words_to_utterances(words, gap=UTT_GAP):
    utts, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > gap or w.get("speaker") != cur[-1].get("speaker")):
            utts.append(cur)
            cur = []
        cur.append(w)
    if cur:
        utts.append(cur)
    return [
        {"start": u[0]["start"], "end": u[-1]["end"],
         "text": " ".join(w["word"] for w in u), "speaker": u[0].get("speaker")}
        for u in utts
    ]


def to_wav(src, dst=None):
    """16 kHz mono wav, the common input for every engine."""
    src = Path(src)
    dst = Path(dst) if dst else ROOT / "audio" / (src.stem + ".wav")
    if not dst.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst)], check=True)
    return dst


def save(engine, audio, words, utterances=None, runtime_s=None, suffix=""):
    OUT.mkdir(exist_ok=True)
    doc = {"engine": engine, "audio": str(audio), "runtime_s": runtime_s,
           "words": words, "utterances": utterances or words_to_utterances(words)}
    path = OUT / f"{Path(audio).stem}.{engine}{suffix}.json"
    path.write_text(json.dumps(doc, indent=1))
    print(f"wrote {path}  ({len(words)} words, {len(doc['utterances'])} utterances, {runtime_s and round(runtime_s, 1)}s)")
    return path
