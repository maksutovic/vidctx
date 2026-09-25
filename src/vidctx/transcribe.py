"""Local transcription with NVIDIA Parakeet TDT 0.6B v2 via parakeet-mlx.

Writes transcript.json:
  {"engine", "model", "runtime_s",
   "words":      [{"word", "start", "end"}],
   "utterances": [{"start", "end", "text"}]}

Utterances are Parakeet's own sentences. Don't re-split on pauses: TDT word
durations run up to the next word, so gaps between words rarely show.
"""
import json
import subprocess
import tempfile
import time
from pathlib import Path

MODEL = "mlx-community/parakeet-tdt-0.6b-v2"


def tokens_to_words(tokens):
    # SentencePiece tokens: a leading space marks the start of a new word.
    words = []
    for t in tokens:
        if not words or t.text.startswith(" "):
            words.append({"word": t.text.strip(), "start": t.start, "end": t.end})
        else:
            words[-1]["word"] += t.text
            words[-1]["end"] = t.end
    return [w for w in words if w["word"]]


def transcribe(video, dest, model_id=MODEL):
    from parakeet_mlx import from_pretrained  # slow import; only when transcribing

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                       check=True)
        model = from_pretrained(model_id)
        t0 = time.time()
        result = model.transcribe(wav, chunk_duration=120, overlap_duration=15)
        runtime = time.time() - t0

    tokens = [t for s in result.sentences for t in s.tokens]
    words = [{**w, "start": round(w["start"], 3), "end": round(w["end"], 3)} for w in tokens_to_words(tokens)]
    utts = [{"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
            for s in result.sentences if s.text.strip()]
    doc = {"engine": "parakeet-mlx", "model": model_id, "runtime_s": round(runtime, 1),
           "words": words, "utterances": utts}
    Path(dest).write_text(json.dumps(doc, indent=1))
    return doc


def empty(dest):
    """For videos without an audio stream."""
    doc = {"engine": None, "model": None, "runtime_s": 0, "words": [], "utterances": []}
    Path(dest).write_text(json.dumps(doc, indent=1))
    return doc
