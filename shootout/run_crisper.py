"""Usage: .venv-crisper/bin/python run_crisper.py <audio-or-video> [verbatim|intended]"""
import sys
import time

from crisperwhisper import CrisperWhisperModel

from common import save, to_wav

MODEL = "nyralabs/CrisperWhisper2.0_large"


def main():
    wav = to_wav(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "verbatim"
    # device="auto" only checks CUDA and falls back to fp16-on-CPU (~40x slower on a Mac).
    # MPS needs transformers<5; 5.x breaks generate() with EncoderDecoderCache.
    model = CrisperWhisperModel(MODEL, device="mps")
    t0 = time.time()
    result = model.transcribe(str(wav), language="en", mode=mode, word_timestamps=True)
    runtime = time.time() - t0
    words = [{"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "speaker": None}
             for w in result.words or [] if w.start is not None and w.word.strip()]
    save("crisper", wav, words, runtime_s=runtime, suffix="" if mode == "verbatim" else "-" + mode)


if __name__ == "__main__":
    main()
