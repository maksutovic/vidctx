"""YouTube (or any yt-dlp supported site) download."""
import re
from pathlib import Path

# 720p is plenty: stills are scaled to 1280 wide anyway. Prefer mp4/m4a so the merge is a remux.
FORMAT = "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b"


def is_url(s):
    return re.match(r"https?://", s) is not None


def download(url, dest_dir):
    from yt_dlp import YoutubeDL

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = {"format": FORMAT, "merge_output_format": "mp4", "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
            "noplaylist": True, "quiet": True, "no_warnings": True, "noprogress": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    path = Path(info["requested_downloads"][0]["filepath"])
    meta = {
        "source": info.get("webpage_url", url),
        "id": info["id"],
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "chapters": [{"start": c["start_time"], "title": c["title"]} for c in info.get("chapters") or []],
    }
    return path, meta
