"""Audio ground-truth check for utterance starts.

For every Deepgram word that follows a >=0.5 s pause (i.e. an utterance start), find
the first sustained energy onset in the audio near where the engines place it, and
measure each engine's start time against that onset. The search window is built from
all engines' starts (not Deepgram's alone) and must begin quiet, so clicks/breaths in
the pause don't count as speech.

Usage: .venv-crisper/bin/python onset_check.py <clip-stem> [margin-db]
"""
import json
import statistics as st
import sys

import numpy as np
import soundfile as sf

from compare import match_words

STEM = sys.argv[1]  # clip stem, matching out/<stem>.*.json
MARGIN = float(sys.argv[2]) if len(sys.argv) > 2 else 18
ENGINES = ["deepgram", "parakeet", "speechmatics-melia-1", "crisper"]
P = f"out/{STEM}."

audio, sr = sf.read(f"audio/{STEM}.wav")
hop = sr // 100  # 10 ms frames
db = 20 * np.log10(np.array([np.sqrt(np.mean(audio[i:i + hop] ** 2)) + 1e-9
                             for i in range(0, len(audio) - hop, hop)]))
thr = np.percentile(db, 10) + MARGIN

ref = json.load(open(P + "deepgram.json"))["words"]
maps = {e: ({id(w): w for w in ref} if e == "deepgram" else
            {id(a): b for a, b in match_words(ref, json.load(open(P + e + ".json"))["words"])[0]})
        for e in ENGINES}

anchors = []
for prev, w in zip(ref, ref[1:]):
    if w["start"] - prev["end"] < 0.5:
        continue
    starts = [maps[e][id(w)]["start"] for e in ENGINES if id(w) in maps[e]]
    if len(starts) < len(ENGINES):
        continue
    a, b = int((min(starts) - 0.3) * 100), int((max(starts) + 0.3) * 100)
    if db[a:a + 5].max() > thr:  # window must start in silence
        continue
    onset = next((i / 100 for i in range(a, b - 4) if (db[i:i + 4] > thr).all()), None)
    if onset is not None:
        anchors.append((w, onset))

print(f"threshold floor+{MARGIN:.0f} dB, {len(anchors)} clean anchors\n")
print("| Engine | Median |error| ms | Median signed ms (+ = late) | ≤50ms % | ≤100ms % |")
print("|---|---|---|---|---|")
for e in ENGINES:
    errs = [maps[e][id(w)]["start"] - onset for w, onset in anchors]
    ab = [abs(x) for x in errs]
    print(f"| {e} | {1000 * st.median(ab):.0f} | {1000 * st.median(errs):+.0f} | "
          f"{100 * sum(x <= .05 for x in ab) / len(ab):.0f} | {100 * sum(x <= .1 for x in ab) / len(ab):.0f} |")
