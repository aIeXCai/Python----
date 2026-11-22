#!/usr/bin/env python3
"""单端口服务器：对外只暴露一个端口，内部转发给 Django，并托管前端静态包。

- /api/, /admin/, /static/, /media/, /internal/  → 反向代理到 127.0.0.1:8000 (Django)
- 其他路径 → 先找 web/ 下的真实文件，找不到则返回 web/index.html（前端路由回退）
"""
import http.client
import json
import mimetypes
import os
import posixpath
import shutil
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
UPSTREAM_HOST = os.environ.get("UPSTREAM_HOST", "127.0.0.1")
UPSTREAM_PORT = int(os.environ.get("UPSTREAM_PORT", "8000"))
PORT = int(os.environ.get("PORT", "3000"))

PROXY_PREFIXES = (
    "/api/", "/api", "/admin", "/static/", "/media/", "/internal/",
)
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}

mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


def should_proxy(path):
    return any(path == p.rstrip("/") or path.startswith(p) for p in PROXY_PREFIXES)


class Handler(BaseHTTPRequestHandler):
    server_version = "PyLearnPortal/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 精简日志
        sys.stderr.write("[portal] %s\n" % (fmt % args))

    # ---------- 静态文件 ----------
    def _safe_path(self, raw_path):
        path = urllib.parse.unquote(urllib.parse.urlsplit(raw_path).path)
        normalized = posixpath.normpath(path)
        if normalized.startswith("..") or "/../" in normalized:
            return None
        return os.path.join(WEB_DIR, normalized.lstrip("/"))

    def _send_file(self, full_path, status=200):
        ctype = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
        try:
            size = os.path.getsize(full_path)
            fh = open(full_path, "rb")
        except OSError:
            self._send_error_page(404, "Not Found")
            return
        with fh:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(size))
            if "/assets/" in full_path:
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            else:
                self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if self.command != "HEAD":
                shutil.copyfileobj(fh, self.wfile)

    def _send_error_page(self, code, message):
        body = ("<h1>%d %s</h1>" % (code, message)).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # ---------- 反向代理 ----------
    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        headers = {}
        app_auth = self.headers.get("X-Auth-Token")
        for key, value in self.headers.items():
            lower = key.lower()
            if lower in HOP_BY_HOP:
                continue
            # 平台边缘网关会用它自己的 Bearer 令牌覆盖 Authorization，
            # 应用自身的登录凭据改由 X-Auth-Token 携带，在这里还原。
            if lower == "x-auth-token":
                continue
            if lower == "authorization" and app_auth:
                continue
            headers[key] = value
        if app_auth:
            headers["Authorization"] = app_auth
        # 保留原始 Host（对外域名），否则 Django 的 CSRF Origin 校验与绝对链接会错乱
        headers["Host"] = self.headers.get("Host", "%s:%d" % (UPSTREAM_HOST, UPSTREAM_PORT))
        headers["X-Forwarded-For"] = self.headers.get("X-Forwarded-For", self.client_address[0])
        headers["X-Forwarded-Proto"] = self.headers.get("X-Forwarded-Proto", "https")
        if body is not None:
            headers["Content-Length"] = str(len(body))

        conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=120)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            upstream = conn.getresponse()
            data = upstream.read()
        except Exception as exc:  # Django 未就绪或崩溃
            self.log_message("upstream error: %s", exc)
            self._send_error_page(502, "后端服务暂时不可用，请稍后刷新")
            return
        finally:
            conn.close()

        self.send_response(upstream.status, upstream.reason)
        for key, value in upstream.getheaders():
            if key.lower() in HOP_BY_HOP:
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    # ---------- 分发 ----------
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _status(self):
        """运行状态与数据库概况（仅聚合数量，不含任何个人数据）。"""
        import sqlite3
        import time

        info = {"now": time.strftime("%Y-%m-%d %H:%M:%S"), "db_exists": False}
        db_path = os.path.join(ROOT, "data", "db.sqlite3")
        if not os.path.isfile(db_path):
            return info
        info["db_exists"] = True
        stat = os.stat(db_path)
        info["db_mtime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        info["db_size_mb"] = round(stat.st_size / 1048576, 1)
        queries = {
            "users": "select count(*) from users_customuser",
            "students": "select count(*) from users_customuser where role='student'",
            "quiz_sessions": "select count(*) from info_tech_quizsession",
            "quiz_submissions": "select count(*) from info_tech_quizsubmission",
        }
        try:
            con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True, timeout=5)
            for key, sql in queries.items():
                try:
                    info[key] = con.execute(sql).fetchone()[0]
                except sqlite3.Error:
                    info[key] = None
            con.close()
        except sqlite3.Error as exc:
            info["error"] = str(exc)
        return info

    def _dispatch(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/__portal_health":
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/__status":
            body = json.dumps(self._status(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/__echo":
            # 诊断用：只回显「认证头是否存在 / 方案 / 长度」，绝不回显凭据原文
            auth = self.headers.get("Authorization") or ""
            info = {
                "has_authorization": bool(auth),
                "scheme": auth.split(" ")[0] if auth else None,
                "length": len(auth),
                "has_cookie": bool(self.headers.get("Cookie")),
                "header_names": sorted(k.lower() for k in self.headers.keys()),
            }
            body = json.dumps(info, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/__version":
            version_file = os.path.join(ROOT, "VERSION")
            text = ""
            if os.path.isfile(version_file):
                with open(version_file, encoding="utf-8") as fh:
                    text = fh.read().strip()
            body = ("{\"version\":%s}" % json.dumps(text)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if should_proxy(path):
            self._proxy()
            return

        full = self._safe_path(self.path)
        if full and os.path.isfile(full):
            self._send_file(full)
            return
        index = os.path.join(WEB_DIR, "index.html")
        if os.path.isfile(index):
            self._send_file(index)
        else:
            self._send_error_page(404, "前端构建产物缺失")

    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PUT(self):
        self._dispatch()

    def do_PATCH(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def do_OPTIONS(self):
        self._dispatch()


def main():
    if not os.path.isdir(WEB_DIR):
        sys.exit("缺少 web/ 前端产物，请先执行 deploy/build_public.sh")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print("[portal] listening on 0.0.0.0:%d -> %s:%d" % (PORT, UPSTREAM_HOST, UPSTREAM_PORT), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
