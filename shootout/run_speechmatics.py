"""Usage: SPEECHMATICS_API_KEY=... python run_speechmatics.py <audio-or-video> [melia-1|standard|enhanced]

Region defaults to eu1; set SPEECHMATICS_REGION=us1 for the US endpoint.
Standard library only, so any python3 works.
"""
import json
import os
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from common import save, to_wav

for env in (Path(__file__).parent / ".env.local", Path(__file__).parent.parent / ".env.local"):
    if env.exists():
        for line in env.read_text().splitlines():
            k, sep, v = line.partition("=")
            if sep and not k.strip().startswith("#"):
                os.environ.setdefault(k.strip().removeprefix("export "), v.strip().strip("'\""))

KEY = os.environ["SPEECHMATICS_API_KEY"]
BASE = f"https://{os.environ.get('SPEECHMATICS_REGION', 'eu1')}.asr.api.speechmatics.com/v2"


def request(method, path, body=None, content_type=None):
    req = urllib.request.Request(BASE + path, data=body, method=method,
                                 headers={"Authorization": f"Bearer {KEY}"})
    if content_type:
        req.add_header("Content-Type", content_type)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def submit(wav, model):
    config = {"type": "transcription", "transcription_config": {
        "model": model, "language": "multi" if model == "melia-1" else "en", "diarization": "speaker"}}
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="config"\r\n\r\n{json.dumps(config)}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="data_file"; filename="{wav.name}"\r\n'
        f'Content-Type: audio/wav\r\n\r\n'.encode() + wav.read_bytes() + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return request("POST", "/jobs", b"".join(parts), f"multipart/form-data; boundary={boundary}")["id"]


def to_words(results):
    words = []
    for r in results:
        alt = r["alternatives"][0]
        if r["type"] == "punctuation" and words:
            words[-1]["word"] += alt["content"]
        elif r["type"] == "word":
            words.append({"word": alt["content"], "start": r["start_time"], "end": r["end_time"],
                          "speaker": alt.get("speaker")})
    return words


def main():
    wav = to_wav(sys.argv[1])
    model = sys.argv[2] if len(sys.argv) > 2 else "melia-1"
    t0 = time.time()
    job = submit(wav, model)
    print("job", job)
    while (status := request("GET", f"/jobs/{job}")["job"]["status"]) == "running":
        time.sleep(5)
    if status != "done":
        sys.exit(f"job {job} ended with status {status}")
    transcript = request("GET", f"/jobs/{job}/transcript?format=json-v2")
    runtime = time.time() - t0
    raw = Path(__file__).parent / "out" / f"{wav.stem}.speechmatics-{model}.raw.json"
    raw.parent.mkdir(exist_ok=True)
    raw.write_text(json.dumps(transcript, indent=1))
    save(f"speechmatics-{model}", wav, to_words(transcript["results"]), runtime_s=runtime)


if __name__ == "__main__":
    main()
