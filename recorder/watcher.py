from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib import request


def _resolve_data_dir() -> Path:
    override = os.environ.get("RECORDER_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local_app_data:
            return Path(local_app_data) / "EuicStatRecorder"
    return Path(__file__).resolve().parent


DATA_DIR = _resolve_data_dir()


def post_line(line: str, url: str) -> None:
    payload = json.dumps({"line": line}).encode("utf-8")
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=2) as response:
            response.read()
    except Exception:
        pass


def post_replay_file(url: str) -> bool:
    payload = json.dumps({}).encode("utf-8")
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=8) as response:
            response.read()
        return True
    except Exception:
        return False


def _load_position(state_path: Path) -> int:
    if state_path.exists():
        try:
            return int(state_path.read_text().strip())
        except Exception:
            return 0
    return 0


def _save_position(state_path: Path, position: int) -> None:
    try:
        state_path.write_text(str(position))
    except Exception:
        pass


def _read_new_lines(path: Path, position: int, url: str) -> int:
    if not path.exists():
        return position
    try:
        size = path.stat().st_size
        if size < position:
            position = 0
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            handle.seek(position)
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                post_line(line, url)
            return handle.tell()
    except Exception:
        return position


def tail_file(path: Path, state_path: Path, url: str) -> None:
    position = _load_position(state_path)
    while True:
        position = _read_new_lines(path, position, url)
        _save_position(state_path, position)
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
    position = 0
    state_path: Path | None = None
    warned_no_files = False
    while True:
        latest = find_latest_log(log_dir)
        if latest is None:
            if not warned_no_files:
                print(f"No .txt logs found in {log_dir}. Waiting for new logs...")
                warned_no_files = True
            time.sleep(1)
            continue
        warned_no_files = False
        if latest and latest != current_file:
            current_file = latest
            state_path = current_file.with_suffix(current_file.suffix + ".offset")
            position = _load_position(state_path)
            print(f"Following log file: {current_file}")
        if current_file and state_path:
            position = _read_new_lines(current_file, position, url)
            _save_position(state_path, position)
        time.sleep(0.5)


def watch_replay_file(replay_file: Path, url: str) -> None:
    print(f"Watching replay file: {replay_file}")
    while True:
        if not replay_file.exists():
            time.sleep(1)
            continue
        try:
            text = replay_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            time.sleep(1)
            continue
        if not text.strip():
            time.sleep(1)
            continue
        ok = post_replay_file(url)
        if not ok:
            time.sleep(2)
            continue
        time.sleep(1)


def _default_log_dirs() -> list[Path]:
    candidates: list[Path] = []
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    home = Path.home()

    if appdata:
        candidates.append(Path(appdata) / "Pokemon Showdown" / "Logs")
        candidates.append(Path(appdata) / "pokemon-showdown" / "logs")
    if localappdata:
        candidates.append(Path(localappdata) / "Pokemon Showdown" / "Logs")
    candidates.append(home / "Documents" / "Pokemon Showdown" / "Logs")

    return [path for path in candidates if path.exists()]


def main() -> None:
    log_path_value = os.environ.get("SHOWDOWN_LOG_PATH", "")
    log_dir_value = os.environ.get("SHOWDOWN_LOG_DIR", "")
    log_path = Path(log_path_value).expanduser() if log_path_value else None
    log_dir = Path(log_dir_value).expanduser() if log_dir_value else None

    replay_file_value = os.environ.get("SHOWDOWN_REPLAY_FILE", "")
    replay_mode = os.environ.get("SHOWDOWN_REPLAY_MODE", "").strip().lower() in {"1", "true", "yes"}
    replay_file = Path(replay_file_value).expanduser() if replay_file_value else None

    api_url = os.environ.get(
        "SHOWDOWN_API_URL", "http://127.0.0.1:5000/api/ingest_line"
    )
    replay_api_url = os.environ.get(
        "SHOWDOWN_REPLAY_API_URL", "http://127.0.0.1:5000/api/ingest_replay_file"
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if replay_mode:
        target = replay_file or (DATA_DIR / "replays.txt")
        watch_replay_file(target, replay_api_url)
        return

    if log_path:
        print(f"Watching log file: {log_path}")
        state_path = log_path.with_suffix(".offset")
        tail_file(log_path, state_path, api_url)
        return

    if log_dir:
        print(f"Watching log directory: {log_dir}")
        watch_directory(log_dir, api_url)
        return

    detected_dirs = _default_log_dirs()
    if detected_dirs:
        print(f"Auto-detected log directory: {detected_dirs[0]}")
        watch_directory(detected_dirs[0], api_url)
        return

    if replay_file:
        watch_replay_file(replay_file, replay_api_url)
        return

    fallback = DATA_DIR / "live_log.txt"
    print(f"Watching fallback file: {fallback}")
    state_path = fallback.with_suffix(".offset")
    tail_file(fallback, state_path, api_url)


if __name__ == "__main__":
    main()
