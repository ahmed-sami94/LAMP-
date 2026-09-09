"""Authenticated owner dashboard. Privileged tasks go through the local worker."""
import base64
from datetime import timedelta
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, redirect, render_template, request, session, Response
import requests
from common import STATE, rpc


def create_app(config=None):
    config = config or json.loads((STATE / "panel.json").read_text())
    app = Flask(__name__)
    app.config.update(SECRET_KEY=config["key"], SESSION_COOKIE_NAME="lamp_session", SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Strict", SESSION_COOKIE_SECURE=config["mode"] == "hosting",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=2), MAX_CONTENT_LENGTH=128 * 1024 * 1024,
                      MAX_FORM_MEMORY_SIZE=65536, MAX_FORM_PARTS=32)

    @app.before_request
    def protect():
        if request.host.split(":")[0].lower() != config["host"]:
            abort(400)
        peer = request.headers.get("X-Lamp-Client", request.remote_addr)
        try:
            trusted = any(ipaddress.ip_address(peer) in ipaddress.ip_network(net) for net in config["proxies"])
        except ValueError:
            trusted = False
        if config["mode"] == "hosting" and not (trusted and request.headers.get("X-Forwarded-Proto") == "https"):
            abort(400, "HTTPS through a configured trusted proxy is required.")
        session.setdefault("csrf", secrets.token_urlsafe(32))
        public = request.endpoint in ("login", "static")
        if not public and not session.get("authenticated"):
            if request.path.startswith("/api/"):
                abort(401)
            return redirect("/login")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("Origin")
            expected_scheme = "https" if config["mode"] == "hosting" else "http"
            if origin and origin != expected_scheme + "://" + request.host:
                abort(403)
            if request.path.startswith(("/phpmyadmin/", "/filebrowser/")):
                # Embedded tools keep native CSRF; cross-origin writes are denied here too.
                if not origin and urlsplit(request.headers.get("Referer", "")).netloc != request.host:
                    abort(403)
            else:
                csrf = request.headers.get("X-CSRF-Token", request.form.get("csrf", ""))
                if not csrf or not hmac.compare_digest(csrf, session["csrf"]):
                    abort(403)

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "same-origin"
        if not request.path.startswith(("/phpmyadmin/", "/filebrowser/")):
            response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if config["mode"] == "hosting":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            try:
                if rpc("login", username=request.form.get("username", ""), password=request.form.get("password", "")):
                    session.clear()
                    session.update(authenticated=True, csrf=secrets.token_urlsafe(32))
                    session.permanent = True
                    return redirect("/")
                error = "Sign-in failed. Check your credentials."
            except ValueError as exc:
                error = str(exc)
        return render_template("login.html", error=error), 401 if error else 200

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/")
    @app.get("/mo")
    def index():
        return render_template("index.html", host=config["host"], mode=config["mode"])

    @app.get("/api/overview")
    def overview():
        return jsonify(rpc("overview"))

    @app.post("/api/actions/<action>")
    def action(action):
        if action not in ("site.create", "php.update", "backup.create", "backup.schedule", "backup.restore"):
            abort(404)
        data = request.get_json()
        if not isinstance(data, dict) or len(json.dumps(data)) > 12000:
            abort(400)
        return jsonify(rpc(action, **data)), 202

    @app.errorhandler(ValueError)
    def value_error(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(OSError)
    def unavailable(error):
        return jsonify(error="The local worker is unavailable. Check container health."), 503

    @app.route("/phpmyadmin")
    @app.route("/filebrowser")
    def tool_slash():
        return redirect(request.path + "/")

    @app.route("/phpmyadmin/", defaults={"path": ""}, methods=["GET", "POST"])
    @app.route("/phpmyadmin/<path:path>", methods=["GET", "POST"])
    @app.route("/filebrowser/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    @app.route("/filebrowser/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def proxy(path):
        is_files = request.path.startswith("/filebrowser/")
        base = "http://127.0.0.1:" + ("8081" if is_files else "8088")
        forwarded = {key: value for key, value in request.headers.items() if key.lower() in
                     ("content-type", "accept", "range", "if-none-match", "cookie", "referer", "origin", "x-requested-with")}
        forwarded["Host"] = request.host
        forwarded["Accept-Encoding"] = "identity"
        if is_files:
            def b64(value):
                return base64.urlsafe_b64encode(value).rstrip(b"=")
            header = b64(b'{"alg":"HS256","typ":"JWT"}')
            body = b64(json.dumps({"sub": "lamp-owner", "exp": int(time.time()) + 60}).encode())
            unsigned = header + b"." + body
            forwarded["X-Lamp-Assertion"] = (unsigned + b"." + b64(hmac.new(config["filebrowser_key"].encode(), unsigned, hashlib.sha256).digest())).decode()
        try:
            upstream = requests.request(request.method, base + request.path, params=request.args,
                headers=forwarded, data=request.get_data(), allow_redirects=False, stream=True, timeout=(3, 120))
        except requests.RequestException:
            abort(502)
        excluded = {"connection", "transfer-encoding", "content-encoding", "content-length", "server", "set-cookie"}
        response = Response(upstream.iter_content(65536), status=upstream.status_code,
                            headers=[(k, v) for k, v in upstream.headers.items() if k.lower() not in excluded])
        for cookie in upstream.raw.headers.getlist("Set-Cookie"):
            response.headers.add("Set-Cookie", cookie)
        response.call_on_close(upstream.close)
        return response

    return app


if os.environ.get("LAMP_TESTING") != "1":
    app = create_app()
