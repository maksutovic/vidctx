"""Usage: python load_deepgram.py <deepgram.json> <audio-or-video>

Converts the Deepgram golden transcript into the shared schema, keeping its
native utterances (utterances=true) as the reference timeline.
"""
import json
import sys
from pathlib import Path

from common import save, to_wav


def main():
    dg = json.loads(Path(sys.argv[1]).read_text())
    wav = to_wav(sys.argv[2])
    words = [{"word": w.get("punctuated_word", w["word"]), "start": w["start"], "end": w["end"],
              "speaker": w.get("speaker")}
             for w in dg["results"]["channels"][0]["alternatives"][0]["words"]]
    utts = [{"start": u["start"], "end": u["end"], "text": u["transcript"], "speaker": u.get("speaker")}
            for u in dg["results"].get("utterances", [])]
    save("deepgram", wav, words, utterances=utts or None)


if __name__ == "__main__":
    main()
