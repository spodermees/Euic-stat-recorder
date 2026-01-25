from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib import request


def post_line(line: str, url: str) -> None:
    payload = json.dumps({"line": line}).encode("utf-8")
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=2) as response:
            response.read()
    except Exception:
        pass


def tail_file(path: Path, state_path: Path, url: str) -> None:
    position = 0
    if state_path.exists():
        try:
            position = int(state_path.read_text().strip())
        except Exception:
            position = 0

    while True:
        if not path.exists():
            time.sleep(1)
            continue

        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            handle.seek(position)
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                post_line(line, url)
            position = handle.tell()

        state_path.write_text(str(position))
        time.sleep(0.5)


def find_latest_log(log_dir: Path) -> Path | None:
    if not log_dir.exists():
        return None
    candidates = [p for p in log_dir.glob("*.txt") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def watch_directory(log_dir: Path, url: str) -> None:
    current_file: Path | None = None
    while True:
        latest = find_latest_log(log_dir)
        if latest and latest != current_file:
            current_file = latest
        if current_file:
            state_path = current_file.with_suffix(current_file.suffix + ".offset")
            tail_file(current_file, state_path, url)
        time.sleep(1)


def main() -> None:
    log_path_value = os.environ.get("SHOWDOWN_LOG_PATH", "")
    log_dir_value = os.environ.get("SHOWDOWN_LOG_DIR", "")
    log_path = Path(log_path_value).expanduser() if log_path_value else None
    log_dir = Path(log_dir_value).expanduser() if log_dir_value else None

    api_url = os.environ.get(
        "SHOWDOWN_API_URL", "http://127.0.0.1:5000/api/ingest_line"
    )

    if log_path:
        state_path = log_path.with_suffix(".offset")
        tail_file(log_path, state_path, api_url)
        return

    if log_dir:
        watch_directory(log_dir, api_url)
        return

    fallback = Path(__file__).resolve().parent / "live_log.txt"
    state_path = fallback.with_suffix(".offset")
    tail_file(fallback, state_path, api_url)


if __name__ == "__main__":
    main()
