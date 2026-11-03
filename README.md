# Internal Assessment 2: Containerization and Deployment of a Cloud-Native Application

**Student:** Kartik Saste  
**Course assessment:** Cloud Computing, Internal Assessment 2  
**Stack:** Python 3.12 · Flask · Gunicorn · Docker · Kubernetes (kind) · kubectl

For this assessment I built a small Python Flask web app, packaged it into a custom Docker image (`kartik-flask-app:1.0`), and ran it as a Docker container. I then deployed it to a Kubernetes cluster with a **Deployment** (2 replicas) and exposed it with a **NodePort Service**. Each page shows the name of the pod that served it, so you can see the Service spreading requests across both replicas.

---

## 1. Overview

| Item | Details |
|---|---|
| Application | Flask web app with an HTML home page, `/health` and `/api/info` JSON endpoints |
| App server | Gunicorn (2 workers) on port **5000** |
| Docker image | `kartik-flask-app:1.0` (base `python:3.12-slim`, ~126 MB, runs as non-root `appuser`) |
| Kubernetes cluster | `kartik-cluster`, a single-node kind cluster (Kubernetes v1.37) |
| Deployment | `kartik-flask-app`, 2 replicas, health probes, resource limits, downward API env vars |
| Service | `kartik-flask-service`, type **NodePort**, `80 → 5000`, nodePort **30080** |
| Access | `http://localhost:30080` (NodePort) or `http://localhost:8080` (`kubectl port-forward`) |

### Endpoints

| Path | Returns |
|---|---|
| `/` | Styled HTML page: app name, version, **pod/host name**, pod IP, node, server time, uptime |
| `/health` | `{"status":"healthy","pod_name":"...","version":"1.0.0"}`, used by Docker HEALTHCHECK and Kubernetes probes |
| `/api/info` | JSON with all runtime details (pod name, IP, node, namespace, Python version, time, uptime) |

---

## 2. Architecture

```mermaid
flowchart LR
    Dev["Developer<br/>app.py + Dockerfile"] -->|docker build| Img["Docker image<br/>kartik-flask-app:1.0"]
    Img -->|docker run -p 5000:5000| C["Docker container<br/>localhost:5000"]
    Img -->|kind load docker-image| Node

    subgraph Cluster["kind cluster: kartik-cluster"]
        Node["Node: kartik-cluster-control-plane"]
        Deploy["Deployment<br/>kartik-flask-app<br/>replicas: 2"] --> RS["ReplicaSet"]
        RS --> P1["Pod 1<br/>flask-app :5000"]
        RS --> P2["Pod 2<br/>flask-app :5000"]
        Svc["Service: kartik-flask-service<br/>NodePort 30080 → port 80 → targetPort 5000"]
        Svc -->|selector app=kartik-flask-app| P1
        Svc -->|load-balanced| P2
    end

    User["Browser / curl"] -->|localhost:30080| Svc
    User -->|kubectl port-forward 8080:80| Svc
```

**Request flow:** browser → `localhost:30080` → kind node port mapping → Service NodePort `30080` → Service port `80` → kube-proxy picks a ready pod → container port `5000` → Gunicorn → Flask.

---

## 3. Project structure

```
k8s-assignment/
├── app.py                     # Flask application (/, /health, /api/info)
├── templates/index.html       # Styled home page
├── requirements.txt           # Pinned runtime dependencies (Flask, gunicorn)
├── requirements-dev.txt       # + pytest for tests
├── tests/test_app.py          # Unit tests for every endpoint
├── Dockerfile                 # Image build recipe
├── .dockerignore              # Keeps build context small and clean
├── kind-config.yaml           # kind cluster with port 30080 mapped to the host
├── k8s/
│   ├── deployment.yaml        # Kubernetes Deployment (2 replicas)
│   └── service.yaml           # Kubernetes NodePort Service
├── scripts/
│   ├── capture_evidence.sh    # Runs the full build → run → deploy → verify flow and logs it
│   ├── run_and_log.sh         # Helper: run a command and save its output to evidence/logs
│   ├── browser_screenshots.py # Headless Chrome screenshots of the running app
│   └── render_terminal_png.py # Renders the logs as terminal-style PNGs
└── evidence/
    ├── logs/                  # Exact terminal output of every step (.txt)
    └── screenshots/           # PNG screenshots, numbered in step order
```

---

## 4. Prerequisites

- Docker Engine (tested with Docker 26.1)
- kubectl (tested with v1.37)
- kind (tested with v0.33) **or** minikube
- Python 3.12+ (only needed to run the tests locally)

---

## 5. Step-by-step commands

### 5.1 Run the tests (optional)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -v            # 5 passed
```

### 5.2 Build the Docker image
```bash
docker build -t kartik-flask-app:1.0 .
docker images kartik-flask-app
```

### 5.3 Run the container
```bash
docker run -d -p 5000:5000 --name kartik-flask-app kartik-flask-app:1.0
docker ps --filter name=kartik-flask-app        # STATUS shows "(healthy)"
curl http://localhost:5000/health
curl http://localhost:5000/api/info
# open http://localhost:5000 in a browser
```

### 5.4 Create the Kubernetes cluster and load the image
```bash
kind create cluster --config kind-config.yaml
kubectl get nodes
kind load docker-image kartik-flask-app:1.0 --name kartik-cluster
```
> `kind load` copies the local image into the cluster node, so no registry is needed. `imagePullPolicy: IfNotPresent` tells Kubernetes to use that copy.

### 5.5 Deploy
```bash
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
kubectl rollout status deployment/kartik-flask-app
kubectl get pods -o wide
kubectl get deploy
kubectl get svc
kubectl describe svc kartik-flask-service
```

### 5.6 Access the application
```bash
# Option A: NodePort (kind maps host port 30080 to the node)
curl http://localhost:30080/health
# open http://localhost:30080

# Option B: port-forward to the Service
kubectl port-forward svc/kartik-flask-service 8080:80
# open http://localhost:8080

# Show that both replicas are serving traffic
for i in $(seq 1 10); do curl -s http://localhost:30080/health; done
```

### 5.7 Extra demonstrations
```bash
kubectl delete pod <one-pod-name>            # self-healing: a replacement pod is created
kubectl scale deploy/kartik-flask-app --replicas=3
kubectl logs deploy/kartik-flask-app
```

### 5.8 Cleanup
```bash
kubectl delete -f k8s/service.yaml -f k8s/deployment.yaml
kind delete cluster --name kartik-cluster
docker rm -f kartik-flask-app
docker rmi kartik-flask-app:1.0
```

> **Re-running all the evidence:** `scripts/capture_evidence.sh` runs every step above in order and regenerates `evidence/logs` and `evidence/screenshots`.

---

## 6. How containerization works (Dockerfile explained)

A **container** packages the application together with its runtime (Python), libraries (Flask, Gunicorn), and configuration into one portable **image**. The same image runs identically on my laptop, a server, or a Kubernetes cluster, which solves the "it works on my machine" problem.

| Dockerfile instruction | Why I used it |
|---|---|
| `FROM python:3.12-slim` | Small official base image, so the final image is smaller and has less attack surface |
| `LABEL ...` | OCI metadata (title, version, author), visible with `docker inspect` |
| `ENV PYTHONUNBUFFERED=1 ...` | Logs go straight to stdout, no `.pyc` files, no pip cache |
| `WORKDIR /app` | All following commands run inside `/app` |
| `COPY requirements.txt` → `RUN pip install` | **Layer caching:** dependencies are installed in their own layer, so editing `app.py` doesn't reinstall Flask on every build |
| `RUN groupadd/useradd` + `USER appuser` | The app runs as a **non-root** user (UID 10001) for security |
| `COPY --chown=appuser app.py templates/` | Copies only the application code, owned by the app user |
| `EXPOSE 5000` | Documents the port the app listens on |
| `HEALTHCHECK` | Docker calls `/health` every 30 s and marks the container `healthy`/`unhealthy` |
| `CMD ["gunicorn", ...]` | Starts a production WSGI server (not Flask's dev server) with 2 workers |

`.dockerignore` keeps `.git`, the virtualenv, tests, and evidence out of the build context, so the build is faster and the image stays clean.

**Image vs container:** the image is the read-only template (like a class). A container is a running instance of it (like an object). `docker run -p 5000:5000` maps port 5000 on the host to port 5000 in the container.

---

## 7. How the Kubernetes deployment works

### 7.1 Deployment (`k8s/deployment.yaml`)
A **Deployment** describes the *desired state* ("I want 2 copies of this container running"), and Kubernetes continuously works to keep the actual state matching it.

- **`replicas: 2`** runs two identical pods for availability and load sharing.
- **`selector` / `labels`** (`app: kartik-flask-app`) are how the Deployment, its ReplicaSet, and the Service find the right pods.
- **`strategy: RollingUpdate` (`maxUnavailable: 0`, `maxSurge: 1`)** means new versions roll out one pod at a time with no downtime.
- **`image: kartik-flask-app:1.0`** with **`imagePullPolicy: IfNotPresent`** uses the image loaded into the node.
- **`env`**: `APP_VERSION` is a plain value. `POD_NAME`, `POD_NAMESPACE`, `POD_IP` and `NODE_NAME` come from the **downward API**, which is how the web page knows which pod served it.
- **`resources`**: requests (`100m` CPU, `64Mi`) help the scheduler place the pod. Limits (`250m`, `128Mi`) stop one pod from using up the node.
- **`readinessProbe`** on `/health` means a pod only receives traffic once it answers.
- **`livenessProbe`** on `/health` means that if the app hangs, Kubernetes restarts the container.
- **`securityContext`**: `runAsNonRoot`, UID 10001, no privilege escalation.

**Self-healing:** when I deleted a pod, the ReplicaSet immediately created a replacement to get back to 2 replicas (see `23_self_healing`).

### 7.2 Service (`k8s/service.yaml`)
Pods are temporary, and their IPs change whenever they are recreated. A **Service** gives them one **stable virtual IP and DNS name** and **load-balances** traffic across every *ready* pod that matches its selector.

- **`type: NodePort`** exposes the Service on a fixed port (`30080`) of every node, so it can be reached from outside the cluster.
- **`port: 80`** is the Service's port inside the cluster (`kartik-flask-service:80`).
- **`targetPort: 5000`** is the container port that traffic is forwarded to.
- **`nodePort: 30080`** is the port opened on the node. `kind-config.yaml` maps host `30080` to node `30080`, so `http://localhost:30080` works.
- The Service's **EndpointSlice** lists the two pod IPs (`kubectl get endpointslices`).

**Load balancing evidence:** 50 requests to the NodePort were split **24 / 26** between the two pods (`18_load_balancing`).

> **Note on the cluster setup:** kind is configured with `kubeProxyMode: nftables`. My machine's kernel doesn't provide the legacy iptables `statistic` module that the default iptables mode uses for load balancing, and nftables mode does the same job natively.

---

## 8. Screenshot gallery (execution evidence)

The full text output of every command is in [`evidence/logs/`](evidence/logs).

### Part A: Docker

| Step | Screenshot |
|---|---|
| Unit tests pass | ![pytest](evidence/screenshots/01_pytest.png) |
| `docker build` | ![build](evidence/screenshots/02_docker_build.png) |
| `docker images` | ![images](evidence/screenshots/03_docker_images.png) |
| Image labels, user, port, healthcheck | ![inspect](evidence/screenshots/03b_docker_inspect.png) |
| `docker run` | ![run](evidence/screenshots/04_docker_run.png) |
| `docker ps` (healthy) | ![ps](evidence/screenshots/05_docker_ps.png) |
| `curl` to the container | ![curl container](evidence/screenshots/06_curl_container.png) |
| Container logs | ![logs](evidence/screenshots/07_docker_logs.png) |
| App in browser, served from Docker | ![browser docker](evidence/screenshots/30_browser_docker_container.png) |

### Part B: Kubernetes

| Step | Screenshot |
|---|---|
| `kind create cluster` | ![kind create](evidence/screenshots/08_kind_create.png) |
| Cluster info and nodes | ![cluster](evidence/screenshots/09_cluster_info.png) |
| `kind load docker-image` | ![kind load](evidence/screenshots/10_kind_load.png) |
| `kubectl apply` | ![apply](evidence/screenshots/11_kubectl_apply.png) |
| Rollout complete, pods Ready | ![rollout](evidence/screenshots/12_rollout_status.png) |
| `kubectl get pods -o wide` | ![pods](evidence/screenshots/13_get_pods.png) |
| `kubectl get deploy` | ![deploy](evidence/screenshots/14_get_deploy.png) |
| `kubectl get svc` and endpoints | ![svc](evidence/screenshots/15_get_svc.png) |
| `kubectl describe svc` | ![describe svc](evidence/screenshots/16_describe_svc.png) |
| `curl` through the NodePort | ![curl nodeport](evidence/screenshots/17_curl_nodeport.png) |
| Load balancing across both pods | ![lb](evidence/screenshots/18_load_balancing.png) |
| `kubectl port-forward` | ![port-forward](evidence/screenshots/19_port_forward.png) |
| `kubectl describe deploy` (probes, limits, env) | ![describe deploy](evidence/screenshots/20_describe_deploy.png) |
| Downward API env, non-root user, probe logs | ![env](evidence/screenshots/21_pod_env_user_logs.png) |
| Self-healing (pod deleted, then recreated) | ![self-healing](evidence/screenshots/23_self_healing.png) |
| Scaling 2 → 3 → 2 | ![scale](evidence/screenshots/24_scaling.png) |
| Final state (cluster + container running) | ![final](evidence/screenshots/25_final_state.png) |

### Part C: App in the browser through Kubernetes

| Service → Pod 1 | Service → Pod 2 |
|---|---|
| ![pod1](evidence/screenshots/31_browser_k8s_nodeport_pod1.png) | ![pod2](evidence/screenshots/32_browser_k8s_nodeport_pod2.png) |

| Via `kubectl port-forward` | `/health` | `/api/info` |
|---|---|---|
| ![pf](evidence/screenshots/33_browser_k8s_port_forward.png) | ![health](evidence/screenshots/34_browser_k8s_health.png) | ![info](evidence/screenshots/35_browser_k8s_api_info.png) |

---

## 9. Conclusion

The Flask application was containerized with a structured, secure Dockerfile, built into `kartik-flask-app:1.0`, and run successfully as a healthy Docker container. It was then deployed to Kubernetes with a 2-replica Deployment (probes, resource limits, downward API) and exposed through a NodePort Service. Every step is backed by logs and screenshots, and the evidence shows the application reachable through the Service, with traffic balanced across both pods, self-healing, and scaling.
