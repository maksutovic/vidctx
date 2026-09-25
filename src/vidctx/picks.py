"""Frame timestamp rules. Pure functions: transcript in, {second: [reasons]} out.

1. Every utterance start.
2. Pointing words ("this", "here", "look at", "right there"...) at the word's own start.
3. Utterances longer than MAX_GAP get evenly spaced interior stills so no gap exceeds it.
4. Narrated actions ("click", "scroll", "moving down"...) at the verb's start.
Long silent stretches are filled by the caller (they need the video for scene detection).
Everything is rounded to the nearest whole second; picks landing on the same second merge,
then thin() enforces a minimum spacing.
"""
import math
import re
from bisect import bisect_right

MAX_GAP = 8.0
MIN_SPACING = 4

# Pointing words that almost always refer to something on screen.
POINT_WORDS = {"this", "these", "those", "here"}
# "that"/"there" alone are too common ("I think that..."); only count them in phrases.
POINT_PHRASES = [("that", "one"), ("right", "there"), ("over", "there"), ("look", "at"),
                 ("see", "that"), ("in", "there")]

ACTION_RE = re.compile(r"^(click|scroll|select|type|typing|drag|hover|press|tap|open|switch|expand|collapse|"
                       r"toggle|zoom|paste|drop)\w*$")
ACTION_PHRASES = [("go", "to"), ("going", "to", "go"), ("go", "back"), ("moving", "down"), ("moving", "up"),
                  ("move", "down"), ("move", "up"), ("down", "here"), ("up", "here")]


def norm(word):
    w = re.sub(r"[^\w']", "", word.lower())
    return re.sub(r"'s$", "", w)  # here's -> here, that's -> that


def sec(t):
    return int(t + 0.5)


def _phrase_hits(tokens, phrases):
    for i in range(len(tokens)):
        for p in phrases:
            if tuple(tokens[i:i + len(p)]) == p:
                yield i, " ".join(p)


def pick(utterances, words, duration, max_gap=MAX_GAP):
    last = max(0, math.ceil(duration) - 1)  # seeking to the very end yields no frame
    picks = {}

    def add(t, why):
        s = min(max(sec(t), 0), last)
        picks.setdefault(s, [])
        if why not in picks[s]:
            picks[s].append(why)

    for u in utterances:
        add(u["start"], "start")
        dur = u["end"] - u["start"]
        n = math.ceil(dur / max_gap) - 1
        for k in range(1, n + 1):
            add(u["start"] + dur * k / (n + 1), "mid")

    tokens = [norm(w["word"]) for w in words]
    for i, tok in enumerate(tokens):
        if tok in POINT_WORDS:
            add(words[i]["start"], tok)
        elif ACTION_RE.match(tok):
            add(words[i]["start"], tok)
    for i, p in _phrase_hits(tokens, POINT_PHRASES):
        add(words[i]["start"], p)
    for i, p in _phrase_hits(tokens, ACTION_PHRASES):
        add(words[i]["start"], p)
    return picks


def _priority(reasons):
    if any(r not in ("start", "mid") for r in reasons):
        return 2  # pointing / action: the still has to land on this exact second
    return 1 if "start" in reasons else 0


def thin(picks, spacing=MIN_SPACING):
    """Keep picks at least `spacing` seconds apart, preferring pointing/action > start > mid.
    Parakeet sentences average ~4.5 s, so unthinned picks run ~1 per 3 s; 4 s lands near 1 per 8 s
    once identical stills are removed."""
    kept = []
    for s in sorted(picks, key=lambda s: (-_priority(picks[s]), s)):
        if all(abs(s - k) >= spacing for k in kept):
            kept.append(s)
    return {s: picks[s] for s in sorted(kept)}


def gaps(seconds, duration, max_gap=MAX_GAP):
    """(a, b) stretches longer than max_gap with no pick, including the head and tail of the video."""
    last = max(0, math.ceil(duration) - 1)
    edges = [0] + sorted(seconds) + [last]
    return [(a, b) for a, b in zip(edges, edges[1:]) if b - a > max_gap]


def fill_evenly(a, b, max_gap=MAX_GAP):
    n = math.ceil((b - a) / max_gap) - 1
    return [sec(a + (b - a) * k / (n + 1)) for k in range(1, n + 1)]


def utterance_at(utterances, t):
    """The utterance a still at second t was taken under: the latest start <= t (+0.5 for rounding)."""
    starts = [u["start"] for u in utterances]
    i = bisect_right(starts, t + 0.5) - 1
    return utterances[i] if i >= 0 else None


def said_between(utterances, a, b):
    """Utterances overlapping [a, b), ignoring sub-second overlaps from rounding."""
    return [u for u in utterances if u["start"] < b - 0.5 and u["end"] > a + 0.5]
