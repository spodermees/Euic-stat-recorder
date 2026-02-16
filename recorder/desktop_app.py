from __future__ import annotations

import threading
import time
from typing import Optional

import webview
from werkzeug.serving import make_server

from app import DATA_DIR, app


class _ServerThread(threading.Thread):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self._server = make_server(host, port, app)
        self.port = self._server.server_port
        self._ready = threading.Event()

    def run(self) -> None:
        self._ready.set()
        self._server.serve_forever()

    def wait_ready(self, timeout: float = 5.0) -> bool:
        return self._ready.wait(timeout)

    def shutdown(self) -> None:
        self._server.shutdown()


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    server = _ServerThread("127.0.0.1", 0)
    server.start()
    server.wait_ready()

    url = f"http://127.0.0.1:{server.port}"
    window = webview.create_window("Euic Stat Recorder", url, width=1200, height=800)

    try:
        webview.start()
    finally:
        server.shutdown()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
