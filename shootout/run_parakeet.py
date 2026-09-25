"""Usage: .venv-parakeet/bin/python run_parakeet.py <audio-or-video> [hf_model_id]"""
import sys
import time

from parakeet_mlx import from_pretrained

from common import save, to_wav

MODEL = "mlx-community/parakeet-tdt-0.6b-v2"


def tokens_to_words(tokens):
    # SentencePiece tokens: a leading space marks the start of a new word.
    words = []
    for t in tokens:
        if not words or t.text.startswith(" "):
            words.append({"word": t.text.strip(), "start": t.start, "end": t.end, "speaker": None})
        else:
            words[-1]["word"] += t.text
            words[-1]["end"] = t.end
    return [w for w in words if w["word"]]


def main():
    wav = to_wav(sys.argv[1])
    model_id = sys.argv[2] if len(sys.argv) > 2 else MODEL
    model = from_pretrained(model_id)
    t0 = time.time()
    result = model.transcribe(wav, chunk_duration=120, overlap_duration=15)
    runtime = time.time() - t0
    tokens = [t for s in result.sentences for t in s.tokens]
    words = [{**w, "start": round(w["start"], 3), "end": round(w["end"], 3)} for w in tokens_to_words(tokens)]
    # TDT word durations run up to the next word, so pauses rarely show as gaps; use
    # Parakeet's own sentence segmentation as its native utterances instead.
    utts = [{"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(), "speaker": None}
            for s in result.sentences]
    save("parakeet", wav, words, utterances=utts, runtime_s=runtime,
         suffix="" if model_id == MODEL else "-" + model_id.split("-")[-1])


if __name__ == "__main__":
    main()
