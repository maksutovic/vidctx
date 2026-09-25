"""Usage: python compare.py out/<clip>.deepgram.json out/<clip>.*.json

Scores each engine against the Deepgram golden transcript:
  - word agreement: share of golden words the engine also produced (order-aligned)
  - word timing: |start| / |end| deltas on matched words
  - utterance starts: for each golden utterance, distance to the nearest engine utterance
    start, both from the engine's native utterances and from re-splitting its words with
    Deepgram's 0.8 s gap rule (apples-to-apples), plus how often the rounded second
    (the frame the video pipeline would grab) is identical.
Deepgram is a reference, not ground truth: its own word timing is ~63 ms off on TIMIT.
"""
import json
import re
import statistics as st
import sys
from difflib import SequenceMatcher
from pathlib import Path

from common import words_to_utterances


def norm(w):
    w = re.sub(r"\[.*?\]", "", w.lower())  # CrisperWhisper verbatim tags like [um]
    return re.sub(r"[^a-z0-9']", "", w)


def match_words(ref, hyp):
    r = [(norm(w["word"]), w) for w in ref if norm(w["word"])]
    h = [(norm(w["word"]), w) for w in hyp if norm(w["word"])]
    sm = SequenceMatcher(a=[x for x, _ in r], b=[x for x, _ in h], autojunk=False)
    pairs = [(r[b.a + k][1], h[b.b + k][1]) for b in sm.get_matching_blocks() for k in range(b.size)]
    return pairs, len(r), len(h)


def pct(xs, t):
    return 100 * sum(x <= t for x in xs) / len(xs) if xs else 0


def utt_scores(ref_utts, hyp_utts):
    starts = [u["start"] for u in hyp_utts]
    if not starts:
        return {}
    d = [min(abs(u["start"] - s) for s in starts) for u in ref_utts]
    same_sec = sum(any(round(s) == round(u["start"]) for s in starts) for u in ref_utts)
    return {"n": len(hyp_utts), "median_ms": 1000 * st.median(d), "within_250ms": pct(d, 0.25),
            "within_1s": pct(d, 1.0), "same_second": 100 * same_sec / len(ref_utts)}


def score(ref, hyp):
    pairs, nr, nh = match_words(ref["words"], hyp["words"])
    ds = [abs(a["start"] - b["start"]) for a, b in pairs]
    de = [abs(a["end"] - b["end"]) for a, b in pairs]
    signed = [b["start"] - a["start"] for a, b in pairs]
    ref_utts = ref["utterances"]
    return {
        "engine": hyp["engine"], "runtime_s": hyp.get("runtime_s"),
        "words": nh, "recall": 100 * len(pairs) / nr, "precision": 100 * len(pairs) / nh if nh else 0,
        "start_med_ms": 1000 * st.median(ds), "start_p90_ms": 1000 * st.quantiles(ds, n=10)[-1],
        "end_med_ms": 1000 * st.median(de), "bias_ms": 1000 * st.median(signed),
        "start_within_50ms": pct(ds, 0.05), "start_within_100ms": pct(ds, 0.1),
        "utt_native": utt_scores(ref_utts, hyp["utterances"]),
        "utt_resplit": utt_scores(ref_utts, words_to_utterances(hyp["words"])),
    }


def fmt(x, nd=0):
    return "–" if x is None else f"{x:.{nd}f}"


def main():
    ref = json.loads(Path(sys.argv[1]).read_text())
    rows = [score(ref, json.loads(Path(p).read_text())) for p in sys.argv[2:] if p != sys.argv[1] and not p.endswith(".raw.json")]
    print(f"Reference: {sys.argv[1]}  ({len(ref['words'])} words, {len(ref['utterances'])} utterances)\n")
    print("## Words vs Deepgram")
    print("| Engine | Runtime s | Words | Recall % | Precision % | Start Δ median ms | Start Δ p90 ms | End Δ median ms | Bias ms (+ = later) | Start ≤50ms % | Start ≤100ms % |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['engine']} | {fmt(r['runtime_s'], 1)} | {r['words']} | {fmt(r['recall'], 1)} | {fmt(r['precision'], 1)} | "
              f"{fmt(r['start_med_ms'])} | {fmt(r['start_p90_ms'])} | {fmt(r['end_med_ms'])} | {fmt(r['bias_ms'])} | "
              f"{fmt(r['start_within_50ms'])} | {fmt(r['start_within_100ms'])} |")
    print("\n## Utterance starts vs Deepgram utterances (what drives frame picks)")
    print("| Engine | Split | Utterances | Nearest-start Δ median ms | ≤250ms % | ≤1s % | Same rounded second % |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        for kind in ("utt_native", "utt_resplit"):
            u = r[kind]
            label = "native" if kind == "utt_native" else "0.8s gap re-split"
            print(f"| {r['engine']} | {label} | {u.get('n')} | {fmt(u.get('median_ms'))} | {fmt(u.get('within_250ms'))} | "
                  f"{fmt(u.get('within_1s'))} | {fmt(u.get('same_second'))} |")


if __name__ == "__main__":
    main()
