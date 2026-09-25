from vidctx import picks


def words_from(text, start, step=0.3):
    return [{"word": w, "start": start + i * step, "end": start + (i + 1) * step} for i, w in enumerate(text.split())]


def test_utterance_starts_round_to_nearest_second():
    utts = [{"start": 1.52, "end": 2.48, "text": "Hi, Claude."}, {"start": 2.48, "end": 5.36, "text": "Okay."}]
    assert sorted(picks.pick(utts, [], 60)) == [2]  # both round to 2 and merge
    assert picks.pick(utts, [], 60)[2] == ["start"]


def test_long_utterance_gets_evenly_spaced_mids():
    utts = [{"start": 10.0, "end": 34.0, "text": "long"}]
    got = picks.pick(utts, [], 60)
    assert sorted(got) == [10, 18, 26]
    assert all(max(b - a for a, b in zip(s, s[1:])) <= 8 for s in [sorted(got) + [34]])


def test_pointing_words_and_phrases():
    w = words_from("I think that works and look at this over here right there", 20.0)
    got = picks.pick([], w, 60)
    why = {r for rs in got.values() for r in rs}
    assert {"look at", "this", "here", "right there"} <= why
    assert "that" not in why  # bare "that" is not a pointer


def test_action_words():
    w = words_from("let me click Settings then scrolling down", 30.0)
    why = {r for rs in picks.pick([], w, 60).values() for r in rs}
    assert {"click", "scrolling"} <= why


def test_contractions_and_punctuation():
    w = words_from("Here's the thing, this.", 5.0)
    why = {r for rs in picks.pick([], w, 60).values() for r in rs}
    assert {"here", "this"} <= why


def test_picks_clamp_to_last_frame():
    utts = [{"start": 59.8, "end": 60.0, "text": "bye"}]
    assert sorted(picks.pick(utts, [], 60.0)) == [59]


def test_gaps_include_head_and_tail():
    assert picks.gaps([20], 40) == [(0, 20), (20, 39)]
    assert picks.gaps([4, 10], 16) == []


def test_fill_evenly():
    assert picks.fill_evenly(0, 20) == [7, 13]


def test_utterance_at_tolerates_rounding_down():
    utts = [{"start": 2.48, "end": 5.36, "text": "a"}, {"start": 5.36, "end": 8.88, "text": "b"}]
    assert picks.utterance_at(utts, 5)["text"] == "b"
    assert picks.utterance_at(utts, 4)["text"] == "a"
    assert picks.utterance_at(utts, 1) is None


def test_thin_prefers_pointing_over_start_over_mid():
    got = picks.thin({10: ["start"], 12: ["this"], 14: ["mid"], 20: ["start"]}, spacing=4)
    assert got == {12: ["this"], 20: ["start"]}
    assert picks.thin({10: ["mid"], 11: ["start"]}, spacing=4) == {11: ["start"]}
