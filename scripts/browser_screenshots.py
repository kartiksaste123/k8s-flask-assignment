"""Capture headless-Chrome screenshots of the app (localhost only).
Each new browser context opens a fresh TCP connection, so the NodePort Service
load-balances them to different pods; we keep going until both pods are captured."""
import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(__file__))
from render_terminal_png import add_url_bar  # noqa: E402

OUT = "evidence/screenshots"
CHROME = "/usr/bin/google-chrome"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])

    def shot(url, path):
        ctx = b.new_context(viewport={"width": 1280, "height": 860})
        page = ctx.new_page()
        page.goto(url)
        pod = page.inner_text(".pod .value")
        page.screenshot(path=path, full_page=True)
        ctx.close()
        return pod

    print("docker:", shot("http://localhost:5000/", f"{OUT}/30_browser_docker_container.png"))
    seen = {}
    for _ in range(30):
        ctx = b.new_context(viewport={"width": 1280, "height": 860})
        page = ctx.new_page()
        page.goto("http://localhost:30080/")
        pod = page.inner_text(".pod .value")
        if pod not in seen:
            idx = len(seen) + 1
            path = f"{OUT}/3{idx}_browser_k8s_nodeport_pod{idx}.png"
            page.screenshot(path=path, full_page=True)
            seen[pod] = path
        ctx.close()
        if len(seen) == 2:
            break
    for pod, path in seen.items():
        print("nodeport:", pod, path)
    print("port-forward:", shot("http://localhost:8080/", f"{OUT}/33_browser_k8s_port_forward.png"))
    for ep in ("health", "api/info"):
        ctx = b.new_context(viewport={"width": 1000, "height": 520})
        page = ctx.new_page()
        page.goto(f"http://localhost:30080/{ep}")
        page.screenshot(path=f"{OUT}/{34 if ep == 'health' else 35}_browser_k8s_{ep.replace('/', '_')}.png")
        ctx.close()
    b.close()

urls = {
    "30_browser_docker_container.png": "http://localhost:5000/   (Docker container, docker run -p 5000:5000)",
    "31_browser_k8s_nodeport_pod1.png": "http://localhost:30080/   (Kubernetes NodePort Service -> pod 1)",
    "32_browser_k8s_nodeport_pod2.png": "http://localhost:30080/   (Kubernetes NodePort Service -> pod 2)",
    "33_browser_k8s_port_forward.png": "http://localhost:8080/   (kubectl port-forward svc/kartik-flask-service 8080:80)",
    "34_browser_k8s_health.png": "http://localhost:30080/health   (Kubernetes Service)",
    "35_browser_k8s_api_info.png": "http://localhost:30080/api/info   (Kubernetes Service)",
}
for f, u in urls.items():
    p = f"{OUT}/{f}"
    if os.path.exists(p):
        add_url_bar(p, u)
        print("url bar:", p)
