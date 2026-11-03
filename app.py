"""
Kartik's Cloud-Native Flask App
--------------------------------
A small Python web application used to demonstrate containerization with
Docker and deployment on Kubernetes.

Endpoints
  /          -> styled HTML home page (app name, version, pod/host name, time)
  /health    -> JSON health check used by Docker HEALTHCHECK and K8s probes
  /api/info  -> JSON with runtime details about the container / pod
"""
import os
import platform
import socket
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template

APP_NAME = os.getenv("APP_NAME", "Kartik Cloud-Native Flask App")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
START_TIME = datetime.now(timezone.utc)

app = Flask(__name__)


def pod_name() -> str:
    """POD_NAME is injected by the Kubernetes downward API; fall back to hostname."""
    return os.getenv("POD_NAME", socket.gethostname())


def runtime_info() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "pod_name": pod_name(),
        "hostname": socket.gethostname(),
        "pod_ip": os.getenv("POD_IP", "n/a"),
        "node_name": os.getenv("NODE_NAME", "n/a"),
        "namespace": os.getenv("POD_NAMESPACE", "n/a"),
        "environment": "kubernetes" if os.getenv("KUBERNETES_SERVICE_HOST") else "docker/local",
        "python_version": platform.python_version(),
        "server_time_utc": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "uptime_seconds": int((now - START_TIME).total_seconds()),
    }


@app.route("/")
def index():
    return render_template("index.html", info=runtime_info())


@app.route("/health")
def health():
    return jsonify(status="healthy", pod_name=pod_name(), version=APP_VERSION), 200


@app.route("/api/info")
def api_info():
    return jsonify(runtime_info()), 200


@app.errorhandler(404)
def not_found(_err):
    return jsonify(error="not found"), 404


if __name__ == "__main__":
    # Development server only; in the container gunicorn serves the app.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
