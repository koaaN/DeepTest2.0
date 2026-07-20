from __future__ import annotations

import socket
import threading
import time
import webbrowser
from typing import Optional

from flask import Flask, Response, request


INJECT_JS = """
<script>
(function() {
    const originalPrompt = window.prompt;
    window.prompt = function(message, defaultValue) {
        try {
            const data = JSON.parse(message);
            const success = data.success === true || data.ret === 0 || data.code === 0;
            const token = data.token || data.result || data.ticket || data.data;
            if (success && token) {
                fetch('/captcha/callback?token=' + encodeURIComponent(message))
                    .then(function() {
                        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:20px;color:green">Captcha verified. You can close this window.</div>';
                    });
                return null;
            }
        } catch (error) {
            console.error('[CAPTCHA] Invalid callback', error);
        }
        return originalPrompt ? originalPrompt.call(window, message, defaultValue) : null;
    };
})();
</script>
"""


class CaptchaWebServer:
    def __init__(self, port: int = 2137, host: str = "127.0.0.1"):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.app.logger.setLevel(40)
        self.captcha_token: Optional[str] = None
        self.html_content: Optional[str] = None
        self.token_received = threading.Event()
        self.server_thread: Optional[threading.Thread] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.route("/captcha.html")
        def serve_captcha() -> Response:
            if not self.html_content:
                return Response("No captcha HTML loaded", status=404)
            headers = {
                "Content-Security-Policy": (
                    "default-src 'self' 'unsafe-inline' 'unsafe-eval' https: data:; "
                    "img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
                    "connect-src 'self' https:; frame-src 'self' https:"
                ),
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "SAMEORIGIN",
            }
            return Response(self.html_content, mimetype="text/html", headers=headers)

        @self.app.route("/captcha/callback")
        def receive_token() -> Response:
            token = request.args.get("token")
            if not token:
                return Response("Missing token parameter", status=400)
            self.captcha_token = token
            self.token_received.set()
            return Response("OK", mimetype="text/plain")

    def set_html(self, html: str) -> None:
        if "</head>" in html:
            self.html_content = html.replace("</head>", INJECT_JS + "</head>", 1)
        elif "<body" in html:
            self.html_content = html.replace("<body", INJECT_JS + "<body", 1)
        else:
            self.html_content = INJECT_JS + html

    def start(self) -> None:
        if self.server_thread and self.server_thread.is_alive():
            return
        if not self._port_available():
            self.port = self._find_free_port()
        self.server_thread = threading.Thread(
            target=lambda: self.app.run(
                host=self.host,
                port=self.port,
                threaded=True,
                use_reloader=False,
                debug=False,
            ),
            daemon=True,
        )
        self.server_thread.start()
        time.sleep(0.3)

    def wait_for_token(self, timeout: float = 300.0) -> Optional[str]:
        if self.token_received.wait(timeout=timeout):
            return self.captcha_token
        return None

    def get_url(self) -> str:
        return f"http://{self.host}:{self.port}/captcha.html"

    def _port_available(self) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
                handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                handle.bind((self.host, self.port))
            return True
        except OSError:
            return False

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
            handle.bind((self.host, 0))
            return int(handle.getsockname()[1])


def solve_captcha(
    captcha_html: str,
    timeout: float = 300.0,
    auto_open_browser: bool = True,
    verbose: bool = False,
) -> str:
    server = CaptchaWebServer()
    server.set_html(captcha_html)
    server.start()
    url = server.get_url()
    if auto_open_browser:
        opened = webbrowser.open(url)
        if not opened:
            print(f"Open CAPTCHA in your browser: {url}")
    else:
        print(f"Open CAPTCHA in your browser: {url}")
    if verbose:
        print(f"Waiting for CAPTCHA callback at {url}")
    token = server.wait_for_token(timeout=timeout)
    if token is None:
        raise RuntimeError(f"CAPTCHA timeout after {timeout:g} seconds")
    return token
